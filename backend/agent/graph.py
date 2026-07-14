"""
LangGraph StateGraph 定义 —— Bioinformatics Agent 的核心编排引擎。

流程：
  START → planner → search → review_search [HITL 中断]
                              ├── 用户批准 → parse → compare → review_results [HITL 中断]
                              │                                              └── report → END
                              └── 用户调整 → 回到 search（重新检索）

支持：
- 多轮对话（通过 thread_id 关联 checkpoint）
- 人工干预（review_search / review_results 两个中断点）
- 流式输出（astream 逐节点推送状态快照）
- checkpoint 持久化（SqliteSaver，服务重启不丢状态）
"""
import uuid
from typing import Any, AsyncGenerator

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from backend.config import config
from backend.agent.state import ResearchState
from backend.agent.nodes import (
    planner_node,
    search_node,
    review_search_node,
    parse_node,
    compare_node,
    review_results_node,
    report_node,
)
from backend.tools.literature_quality import quality_scorer


def _route_after_search(state: ResearchState) -> str:
    """搜索后的路由：正常→审核，无结果/出错→直接生成错误报告"""
    next_node = state.get("next_node", "review_search")
    if next_node == "report":
        return "report"
    if not state.get("search_results"):
        return "report"  # 无结果直接跳到报告
    return "review_search"


def _route_after_parse(state: ResearchState) -> str:
    """解析后的路由：有数据→对比，无数据→直接生成报告"""
    next_node = state.get("next_node", "compare")
    if next_node == "report":
        return "report"
    if not state.get("parsed_papers"):
        return "report"
    return "compare"


def _route_after_search_review(state: ResearchState) -> str:
    """检索审核后的路由：完全依赖 review_search_node 设置的 next_node，
    不再重复检查 user_feedback / user_adjusted_query，避免路由逻辑分散。
    """
    return state.get("next_node", "parse")


def _route_after_results_review(state: ResearchState) -> str:
    """结果审核后的路由→报告"""
    return "report"


# ── 构建 StateGraph ──

def build_graph() -> StateGraph:
    """构建并编译 StateGraph"""
    graph = StateGraph(ResearchState)

    # 添加节点
    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("review_search", review_search_node)
    graph.add_node("parse", parse_node)
    graph.add_node("compare", compare_node)
    graph.add_node("review_results", review_results_node)
    graph.add_node("report", report_node)

    # 静态边
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "search")

    # 条件边：search 完成后→审核 或 直接报告（无结果时）
    graph.add_conditional_edges("search", _route_after_search, {
        "review_search": "review_search",
        "report": "report",
    })

    # 条件边：审核后的路由
    graph.add_conditional_edges("review_search", _route_after_search_review, {
        "search": "search",
        "parse": "parse",
    })

    # 条件边：parse 完成后→对比 或 直接报告（无文献时）
    graph.add_conditional_edges("parse", _route_after_parse, {
        "compare": "compare",
        "report": "report",
    })

    # compare → review → report
    graph.add_edge("compare", "review_results")
    graph.add_conditional_edges("review_results", _route_after_results_review, {
        "report": "report",
    })
    graph.add_edge("report", END)

    return graph


# ── 全局编译实例 ──

_sqlite_saver_ctx = SqliteSaver.from_conn_string(str(config.DATA_DIR / "checkpoints.db"))
_sqlite_saver = _sqlite_saver_ctx.__enter__()

_compiled_graph = build_graph().compile(
    checkpointer=_sqlite_saver,
    interrupt_before=["review_search", "review_results"],
)


def get_graph():
    """获取编译后的 graph 实例"""
    return _compiled_graph


def get_checkpointer() -> SqliteSaver:
    """获取 SqliteSaver 实例（用于查询和管理 checkpoint）"""
    return _sqlite_saver


# ── 高层 API ──

def new_thread_id() -> str:
    """生成新的对话线程 ID"""
    return uuid.uuid4().hex[:16]


async def run_research(
    query: str,
    max_papers: int = 5,
    thread_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    执行一次完整的研究流程，流式返回每个节点的状态快照。

    用法（FastAPI SSE）:
        async for snapshot in run_research(query="EGFR突变肺癌治疗"):
            yield f"data: {json.dumps(snapshot)}\\n\\n"

    Args:
        query: 用户研究意图
        max_papers: 最大检索文献数
        thread_id: 对话线程 ID（None 则自动生成），同一 thread_id 可支持多轮对话
    """
    graph = get_graph()
    tid = thread_id or new_thread_id()

    initial_state: ResearchState = {
        "thread_id": tid,
        "messages": [],
        "query": query,
        "max_papers": max_papers,
        "plan_summary": "",
        "pubmed_query": "",
        "search_results": [],
        "selected_papers": [],
        "user_action": "",
        "user_approved_search": False,
        "user_selected_ids": [],
        "user_feedback": "",
        "user_adjusted_query": "",
        "interaction_history": [],
        "parsed_papers": {},
        "pdf_available": {},
        "comparison_report": "",
        "final_report": "",
        "execution_log": [],
        "errors": [],
        "current_step": "初始化...",
        "next_node": "",
    }

    config = {"configurable": {"thread_id": tid}}

    try:
        for event in graph.stream(initial_state, config, stream_mode="values"):
            # event 是完整的 ResearchState dict
            yield _to_snapshot(event)
    except Exception as e:
        yield {
            "thread_id": tid,
            "current_step": "执行出错",
            "final_report": "",
            "errors": [f"{type(e).__name__}: {str(e)}"],
            "execution_log": [],
            "sub_tasks": [],
            "plan_summary": "",
            "search_results_count": 0,
            "selected_papers_count": 0,
            "parsed_papers_count": 0,
            "comparison_report": "",
            "papers": [],
        }


async def resume_research(
    thread_id: str,
    user_action: str,  # "approve" | "retry" | "select" | "revise"
    feedback: str = "",
    adjusted_query: str = "",
    selected_ids: list[str] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    从 HITL 中断点恢复执行。

    当 graph 在 review_search 或 review_results 暂停后，
    前端收集用户决定，调用此函数恢复执行。

    Args:
        thread_id: 对话线程 ID
        user_action: "approve"（继续）/ "retry"（重新检索）/ "select"（手动选文献）/ "revise"（调整分析）
        feedback: 用户反馈文本
        adjusted_query: 用户调整后的检索式（仅 retry 时有效）
        selected_ids: 用户手动勾选的 PMID 列表（仅 select 时有效）
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # 获取当前 checkpoint 状态，确定中断在哪个节点
    current_state = graph.get_state(config)

    if current_state is None or current_state.next == ():
        # 没有中断点，可能已执行完毕
        yield {
            "thread_id": thread_id,
            "current_step": "完成",
            "final_report": "",
            "errors": ["无法恢复：没有待处理的中断点"],
            "execution_log": [],
            "sub_tasks": [],
            "plan_summary": "",
            "search_results_count": 0,
            "selected_papers_count": 0,
            "parsed_papers_count": 0,
            "comparison_report": "",
            "papers": [],
        }
        return

    current_values = current_state.values if hasattr(current_state, "values") else {}

    # 根据用户动作更新 state —— user_action 是唯一的路由决策来源
    update_values: dict[str, Any] = {"user_action": user_action}
    history = list(current_values.get("interaction_history", []))

    if user_action == "retry":
        update_values["user_feedback"] = feedback
        update_values["user_adjusted_query"] = adjusted_query
        history.append({
            "stage": "review_search",
            "action": "retry",
            "feedback": feedback,
            "adjusted_query": adjusted_query,
        })
    elif user_action == "revise":
        update_values["user_feedback"] = feedback
        history.append({
            "stage": "review_results",
            "action": "revise",
            "feedback": feedback,
        })
    elif user_action == "select":
        update_values["user_selected_ids"] = selected_ids or []
        history.append({
            "stage": "review_search",
            "action": "select",
            "selected_ids": selected_ids or [],
        })
    elif user_action == "approve":
        pause_point = current_values.get("next_node", "")
        history.append({
            "stage": pause_point or "unknown",
            "action": "approve",
        })

    update_values["interaction_history"] = history

    # 更新 checkpoint
    graph.update_state(config, update_values)

    # 恢复执行
    try:
        for event in graph.stream(None, config, stream_mode="values"):
            yield _to_snapshot(event)
    except Exception as e:
        yield {
            "thread_id": thread_id,
            "current_step": "执行出错",
            "final_report": "",
            "errors": [f"{type(e).__name__}: {str(e)}"],
            "execution_log": [],
            "sub_tasks": [],
            "plan_summary": "",
            "search_results_count": 0,
            "selected_papers_count": 0,
            "parsed_papers_count": 0,
            "comparison_report": "",
            "papers": [],
        }


def get_thread_state(thread_id: str) -> dict | None:
    """查询指定线程的当前状态"""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if state is None:
        return None
    return _to_snapshot(state.values)


# ── 快照序列化 ──

def _to_snapshot(state: dict) -> dict[str, Any]:
    """将 ResearchState 转为前端可用的快照 dict"""
    # 构造 sub_tasks 列表（兼容旧前端格式）
    sub_tasks = _build_sub_tasks(state)

    papers = _build_papers_list(state)
    candidate_papers = _build_candidate_papers_list(state)

    return {
        "thread_id": state.get("thread_id", ""),
        "current_step": state.get("current_step", ""),
        "plan_summary": state.get("plan_summary", ""),
        "sub_tasks": sub_tasks,
        "execution_log": list(state.get("execution_log", [])),
        "search_results_count": len(state.get("search_results", [])),
        "selected_papers_count": len(state.get("selected_papers", [])),
        "parsed_papers_count": len(state.get("parsed_papers", {})),
        "comparison_report": state.get("comparison_report", ""),
        "final_report": state.get("final_report", ""),
        "errors": state.get("errors", []),
        "papers": papers,
        "candidate_papers": candidate_papers,
        # HITL 相关字段
        "is_paused": state.get("next_node", "") in ("review_search", "review_results"),
        "pause_point": state.get("next_node", ""),
        "user_approved_search": state.get("user_approved_search", False),
    }


def _build_sub_tasks(state: dict) -> list[dict[str, Any]]:
    """从当前状态构建任务列表（兼容旧前端 DAGFlow）"""
    tasks = []
    nodes_done = set()

    # 根据 execution_log 推断各节点状态
    logs = state.get("execution_log", [])
    for log in logs:
        if "[Planner]" in log and "完成" in log:
            tasks.append({"id": "planner", "type": "plan", "description": "任务规划", "depends_on": [], "status": "done"})
            nodes_done.add("planner")
        if "[Search Worker]" in log and "筛选完成" in log:
            tasks.append({"id": "search", "type": "search", "description": "文献检索与筛选", "depends_on": ["planner"], "status": "done"})
            nodes_done.add("search")
        if "[Parser Worker]" in log and "完成" in log:
            tasks.append({"id": "parse", "type": "parse", "description": "文献结构化解析", "depends_on": ["search"], "status": "done"})
            nodes_done.add("parse")
        if "[Compare Worker]" in log:
            if "完成" in log or "跳过" in log:
                tasks.append({"id": "compare", "type": "compare", "description": "跨文献对比分析", "depends_on": ["parse"], "status": "done"})
                nodes_done.add("compare")
        if "[Reporter]" in log and "完毕" in log:
            tasks.append({"id": "report", "type": "report", "description": "生成综述报告", "depends_on": ["compare"], "status": "done"})
            nodes_done.add("report")

    # 补充 running/pending 状态的任务
    if "planner" not in nodes_done:
        tasks.append({"id": "planner", "type": "plan", "description": "任务规划", "depends_on": [], "status": "running" if state.get("current_step", "").startswith("Planner") else "pending"})
    if "search" not in nodes_done:
        tasks.append({"id": "search", "type": "search", "description": "文献检索与筛选", "depends_on": ["planner"], "status": "running" if "检索" in state.get("current_step", "") else "pending"})
    if "parse" not in nodes_done:
        tasks.append({"id": "parse", "type": "parse", "description": "文献结构化解析", "depends_on": ["search"], "status": "running" if "解析" in state.get("current_step", "") else "pending"})
    if "compare" not in nodes_done:
        tasks.append({"id": "compare", "type": "compare", "description": "跨文献对比分析", "depends_on": ["parse"], "status": "running" if "对比" in state.get("current_step", "") else "pending"})
    if "report" not in nodes_done:
        tasks.append({"id": "report", "type": "report", "description": "生成综述报告", "depends_on": ["compare"], "status": "running" if "报告" in state.get("current_step", "") else "pending"})

    return tasks


def _build_papers_list(state: dict) -> list[dict[str, Any]]:
    """从解析结果中提取论文详情列表"""
    papers: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for pubmed_id, data in state.get("parsed_papers", {}).items():
        paper_info = data.get("paper_info", {})
        structured = data.get("structured", {})
        validation = data.get("validation", {})

        papers.append({
            "pubmed_id": pubmed_id,
            "title": structured.get("title", paper_info.get("title", "")),
            "abstract": paper_info.get("abstract", ""),
            "authors": _as_list(structured.get("authors", "").split(", ")) or _as_list(paper_info.get("authors", [])),
            "journal": structured.get("journal", paper_info.get("journal", "")),
            "publication_date": str(structured.get("year", paper_info.get("publication_date", ""))),
            "doi": structured.get("doi", paper_info.get("doi", "")),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            "objective": structured.get("objective", ""),
            "method": structured.get("method", ""),
            "target": structured.get("target", ""),
            "key_findings": structured.get("key_findings", ""),
            "conclusion": structured.get("conclusion", ""),
            "validation_warnings": len(validation.get("warnings", [])),
            "validation_corrections": len(validation.get("corrections", [])),
        })
        seen_ids.add(pubmed_id)

    for paper in state.get("selected_papers", []):
        pid = paper.get("pubmed_id", "")
        if pid and pid not in seen_ids:
            papers.append({
                "pubmed_id": pid,
                "title": paper.get("title", ""),
                "abstract": paper.get("abstract", ""),
                "authors": _as_list(paper.get("authors", [])),
                "journal": paper.get("journal", ""),
                "publication_date": paper.get("publication_date", ""),
                "doi": paper.get("doi", ""),
                "url": paper.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"),
                "objective": "", "method": "", "target": "",
                "key_findings": "", "conclusion": "",
                "validation_warnings": 0, "validation_corrections": 0,
            })
            seen_ids.add(pid)

    return papers


def _build_candidate_papers_list(state: dict) -> list[dict[str, Any]]:
    """构建检索审核用的完整候选文献列表。"""
    search_results = state.get("search_results", [])
    if not search_results:
        return []

    selected_ids = [
        paper.get("pubmed_id", "")
        for paper in state.get("selected_papers", [])
        if paper.get("pubmed_id", "")
    ]
    selected_id_set = set(selected_ids)

    scored_by_id = {
        paper.get("pubmed_id", ""): paper
        for paper in quality_scorer.rank_papers(search_results)
    }

    def to_candidate(paper: dict) -> dict[str, Any]:
        pid = paper.get("pubmed_id", "")
        scored = scored_by_id.get(pid, paper)
        return {
            "pubmed_id": paper.get("pubmed_id", ""),
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": _as_list(paper.get("authors", [])),
            "journal": paper.get("journal", ""),
            "publication_date": paper.get("publication_date", ""),
            "doi": paper.get("doi", ""),
            "url": paper.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pubmed_id', '')}/"),
            "objective": "", "method": "", "target": "",
            "key_findings": "", "conclusion": "",
            "quality": scored.get("quality", {}),
            "is_default_selected": pid in selected_id_set,
            "validation_warnings": 0,
            "validation_corrections": 0,
        }

    search_by_id = {
        paper.get("pubmed_id", ""): paper
        for paper in search_results
    }

    # 先展示 LLM 相关性筛出的默认推荐文献；其内部顺序已在 search_node 中按质量重排。
    selected_candidates = [
        to_candidate(search_by_id[pid])
        for pid in selected_ids
        if pid in search_by_id
    ]

    # 其他候选再按项目质量评分排序，方便用户追加选择。
    remaining_ranked = quality_scorer.rank_papers([
        paper for paper in search_results
        if paper.get("pubmed_id", "") not in selected_id_set
    ])
    remaining_candidates = [to_candidate(paper) for paper in remaining_ranked]

    return selected_candidates + remaining_candidates


def _as_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []
