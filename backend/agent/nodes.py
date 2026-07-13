"""
LangGraph 节点函数 —— 每个节点接收 state，返回部分更新的 state dict。
从原有 workers 中提取逻辑，适配 StateGraph 的执行模式。
"""
import re
from backend.tools.llm_client import llm
from backend.tools.pubmed_search import pubmed
from backend.tools.pdf_parser import pdf_parser, ParseResult
from backend.tools.biomedical_terminology import terminology
from backend.tools.search_templates import template_matcher
from backend.tools.literature_quality import quality_scorer
from backend.schemas.literature import LiteratureSchema
from backend.agent.state import ResearchState

# ═══════════════════════════════════════════════════════════════
# Planner Node
# ═══════════════════════════════════════════════════════════════

PLANNER_SYSTEM_PROMPT = """你是一个生物医学文献研究规划专家。你的任务是将用户的研究意图拆解为具体的执行步骤。

可用的步骤类型 (type):
- "search": 在 PubMed 中检索相关文献
- "parse": 解析检索到文献的全文（或摘要），提取结构化信息
- "compare": 对比多篇文献的方法、结果和结论
- "report": 汇总所有信息，生成最终文献概览报告

你只需要返回一个 JSON：
{
  "plan_summary": "用一句话概述你的执行计划",
  "steps": ["search: 在PubMed检索关于XXX的文献", "parse: 提取结构化信息", "compare: 跨文献对比", "report: 生成综述报告"]
}

规则：如果用户意图较宽泛，search 应拆为2个不同角度的检索。
"""


def planner_node(state: ResearchState) -> dict:
    """规划节点：将用户意图拆解为执行计划"""
    query = state.get("query", "")
    max_papers = state.get("max_papers", 5)

    logs = list(state.get("execution_log", []))
    logs.append("[Planner] 正在分析研究意图，拆解任务...")
    current_step = "Planner 规划中"

    try:
        result = llm.chat_json(
            user_prompt=f"用户研究意图：\n{query}\n\n请拆解为具体的执行步骤。",
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.1,
        )
        plan_summary = result.get("plan_summary", f"针对 '{query[:60]}' 的系统性文献调研")
        steps = result.get("steps", [
            f"search: 检索 PubMed: {query}",
            "parse: 解析检索结果摘要",
            "compare: 对比分析文献",
            "report: 生成最终报告",
        ])
    except Exception as e:
        logs.append(f"[Planner] LLM 调用失败，使用默认计划: {e}")
        plan_summary = f"针对 '{query[:80]}' 的文献调研"
        steps = [
            f"search: 检索 PubMed: {query}",
            "parse: 解析检索结果",
            "compare: 对比分析",
            "report: 生成报告",
        ]

    logs.append(f"[Planner] 完成。计划: {plan_summary}")
    for i, step in enumerate(steps, 1):
        logs.append(f"  Step {i}: {step}")

    return {
        "plan_summary": plan_summary,
        "execution_log": logs,
        "current_step": current_step,
        "next_node": "search",
    }


# ═══════════════════════════════════════════════════════════════
# Search Node
# ═══════════════════════════════════════════════════════════════

QUERY_BUILD_PROMPT = """你是一个 PubMed 检索专家。请将以下生物医学研究任务转换为 PubMed 检索式。

任务描述：
{description}

用户原始研究意图：
{query}

请返回一个 JSON：
{{
  "pubmed_query": "正式的 PubMed 检索式（英文关键词 + PubMed 语法）",
  "keywords": "提取的核心关键词（逗号分隔）"
}}

规则：
1. 检索式必须使用英文，只包含 PubMed 支持的语法：MeSH 词、布尔运算符 (AND/OR/NOT)
2. 不要包含中文或自然语言描述
"""

SEARCH_FILTER_PROMPT = """你是一个生物医学文献筛选专家。根据用户的研究意图，从检索结果中筛选最相关的文献。

用户意图：{query}

检索结果：
{results_text}

请选出最相关的 {max_papers} 篇文献，按相关性从高到低排序。返回 JSON：
{{
  "selected_ids": ["pubmed_id_1", "pubmed_id_2", ...],
  "reason": "简短的筛选理由"
}}

筛选标准：
1. 优先选择与研究意图直接相关的文献
2. 优先选择近3年发表的文献
3. 优先选择有摘要的文献
"""


def search_node(state: ResearchState) -> dict:
    """检索节点：构建 PubMed 检索式 → 检索 → 筛选"""
    query = state.get("query", "")
    max_papers = state.get("max_papers", 5)
    user_adjusted = state.get("user_adjusted_query", "")
    user_feedback = state.get("user_feedback", "")
    user_selected = state.get("user_selected_ids", [])

    # 继承已有日志，若是 HITL 重试则先清理陈旧的检索/审核日志
    logs = list(state.get("execution_log", []))
    if user_feedback or user_adjusted:
        logs = [l for l in logs if not l.startswith("[Search Worker]") and not l.startswith("[HITL]")]

    # 如果用户手动选了文献，直接跳过往返检索
    if user_selected:
        article_map = {a["pubmed_id"]: a for a in state.get("search_results", [])}
        selected = [article_map[pid] for pid in user_selected if pid in article_map]
        if selected:
            logs.append(f"[Search Worker] 用户手动选择 {len(selected)} 篇文献")
            logs.append("\n".join(f"  - [{p.get('pubmed_id', '?')}] {p.get('title', '')[:80]}" for p in selected))
            return {
                "selected_papers": selected,
                "execution_log": logs,
                "current_step": f"用户选定 {len(selected)} 篇文献",
                "next_node": "parse",
            }

    # 如果用户要求重新搜索，使用调整后的检索式
    search_query = user_adjusted if user_adjusted else query

    if user_feedback:
        logs.append(f"[Search Worker] 根据用户反馈重新搜索: {user_feedback}")

    max_results = max_papers * 3  # 多检索一些供筛选

    # ── Step 1: 构建检索式 ──
    # 优先使用模板匹配
    matched = template_matcher.match(search_query)
    if matched and matched["confidence"] >= 0.4:
        pubmed_query = matched["pubmed_query"]
        logs.append(f"[Search Worker] 模板匹配: {matched['template_id']} (置信度 {matched['confidence']:.2f})")
    else:
        try:
            query_result = llm.chat_json(
                user_prompt=QUERY_BUILD_PROMPT.format(description=search_query, query=query),
                system_prompt="请以 JSON 格式返回 PubMed 检索式。",
                temperature=0.1,
            )
            pubmed_query = query_result.get("pubmed_query", "")
        except Exception:
            pubmed_query = _fallback_query(search_query)

    if not pubmed_query or not pubmed_query.strip():
        pubmed_query = _fallback_query(search_query)

    logs.append(f"[Search Worker] PubMed 检索式: {pubmed_query}")

    # ── Step 2: PubMed 检索 ──
    try:
        articles = pubmed.search(pubmed_query, max_results=max_results)
    except Exception as e:
        logs.append(f"[Search Worker] 检索失败: {e}")
        return {
            "search_results": [],
            "selected_papers": [],
            "execution_log": logs,
            "errors": [f"PubMed 检索失败: {e}"],
            "current_step": "检索失败",
            "next_node": "report",
        }

    logs.append(f"[Search Worker] 检索到 {len(articles)} 篇文献")

    if not articles:
        logs.append("[Search Worker] 无检索结果")
        return {
            "search_results": [],
            "selected_papers": [],
            "execution_log": logs,
            "current_step": "检索完成（无结果）",
            "next_node": "report",
        }

    # ── Step 3: LLM 筛选 + 规则重排 ──
    results_text = "\n\n".join(
        f"[{a['pubmed_id']}] {a['title']}\n{a.get('abstract', '')[:300]}..."
        for a in articles
    )

    try:
        filter_result = llm.chat_json(
            user_prompt=SEARCH_FILTER_PROMPT.format(
                query=query,
                results_text=results_text,
                max_papers=max_papers,
            ),
            system_prompt="请以 JSON 格式返回筛选结果。",
            temperature=0.1,
        )
        selected_ids = filter_result.get("selected_ids", [])
    except Exception:
        selected_ids = [a["pubmed_id"] for a in articles[:max_papers]]

    article_map = {a["pubmed_id"]: a for a in articles}
    selected = [article_map[pid] for pid in selected_ids if pid in article_map]

    # 规则层：质量重排序
    if selected:
        selected = quality_scorer.rank_papers(selected)

    logs.append(
        f"[Search Worker] 筛选完成: {len(selected)} 篇相关文献\n"
        + "\n".join(f"  - [{p.get('pubmed_id', '?')}] {p.get('title', '')[:80]}" for p in selected)
    )

    return {
        "search_results": articles,
        "selected_papers": selected,
        "execution_log": logs,
        "current_step": f"检索完成，找到 {len(selected)} 篇相关文献",
        "user_action": "",              # 重置，等待下一轮 HITL 设置
        "user_approved_search": False,
        "user_feedback": "",
        "user_adjusted_query": "",
        "next_node": "review_search",
    }


def _fallback_query(user_query: str) -> str:
    """LLM 不可用时从用户输入提取英文关键词"""
    combined = user_query
    english_terms = re.findall(r'[A-Za-z0-9\-+]+', combined)
    meaningful = [t for t in english_terms if len(t) > 2]
    if meaningful:
        return " AND ".join(meaningful[:5])
    return user_query.strip().replace(" ", " AND ")


# ═══════════════════════════════════════════════════════════════
# Review Search Node (HITL 中断点)
# ═══════════════════════════════════════════════════════════════

def review_search_node(state: ResearchState) -> dict:
    """检索审核节点——HITL 中断点。

    路由决策完全依赖 state["user_action"]（由 resume_research 在前端调用时设置），
    不再重复检查 user_feedback / user_adjusted_query，保持路由逻辑单一来源。
    """
    user_action = state.get("user_action", "")
    user_selected = state.get("user_selected_ids", [])
    logs = list(state.get("execution_log", []))

    if user_action == "retry":
        logs.append(f"[HITL] 用户要求调整检索: {state.get('user_feedback', '') or state.get('user_adjusted_query', '')}")
        return {
            "user_approved_search": False,
            "execution_log": logs,
            "next_node": "search",
            "current_step": "根据用户反馈重新检索...",
        }

    if user_action == "select" or user_selected:
        logs.append(f"[HITL] 用户手动选择 {len(user_selected)} 篇文献，进入解析")
        return {
            "user_approved_search": True,
            "execution_log": logs,
            "next_node": "parse",
            "current_step": "用户已选择文献，进入解析...",
        }

    # approve 或其他默认情况
    logs.append("[HITL] 检索审核通过，进入文献解析")
    return {
        "user_approved_search": True,
        "execution_log": logs,
        "next_node": "parse",
        "current_step": "检索审核通过，进入文献解析...",
    }


# ═══════════════════════════════════════════════════════════════
# Parse Node
# ═══════════════════════════════════════════════════════════════

PARSE_SYSTEM_PROMPT = """你是一个生物医学文献信息提取专家。请从以下文献内容中提取关键信息。

请提取以下字段并以 JSON 格式返回：
{
  "objective": "研究目标（1-2句话）",
  "method": "使用的实验方法、技术手段",
  "target": "研究的靶点、基因、蛋白质或疾病",
  "biomarker": "涉及的生物标志物（如无可留空）",
  "sample_size": "样本量（如无可留空）",
  "model_system": "模型系统，如细胞系、动物模型等",
  "key_findings": "核心发现（2-3句话）",
  "result_value": "关键数值结果，如p值、效应量等",
  "conclusion": "结论（1-2句话）",
  "figures_summary": "图表内容概述（如无图表可留空）",
  "limitations": "研究局限性（如未提及可留空）"
}

只提取文献中明确提到的内容，不要编造。如果某字段信息不明，填入空字符串。
"""


def parse_node(state: ResearchState) -> dict:
    """解析节点：对选中的每篇文献提取结构化数据，并进行术语校验"""
    papers = state.get("selected_papers", [])
    logs = list(state.get("execution_log", []))
    errors = []

    if not papers:
        logs.append("[Parser Worker] 没有需要解析的文献")
        return {
            "parsed_papers": {},
            "execution_log": logs,
            "current_step": "无文献需要解析",
            "next_node": "report",
        }

    parsed = dict(state.get("parsed_papers", {}))
    current_step = f"解析中: 共 {len(papers)} 篇文献..."

    for i, paper in enumerate(papers):
        pubmed_id = paper.get("pubmed_id", f"unknown_{i}")
        title = paper.get("title", "N/A")

        logs.append(f"[Parser Worker] ({i+1}/{len(papers)}) 解析: {title[:80]}")

        pdf_path = state.get("pdf_available", {}).get(pubmed_id, "")
        content_text = ""

        if pdf_path:
            try:
                parse_result: ParseResult = pdf_parser.parse(pdf_path, prefer_mineru=True)
                content_text = parse_result.full_text[:8000]
                logs.append(f"  PDF 已解析: {parse_result.page_count} 页")
            except Exception as e:
                logs.append(f"  PDF 解析失败，回退到摘要: {e}")

        if not content_text:
            content_text = f"标题: {title}\n摘要: {paper.get('abstract', '无摘要')}"

        # LLM 提取
        try:
            extracted = llm.chat_json(
                user_prompt=f"文献内容：\n{content_text[:6000]}",
                system_prompt=PARSE_SYSTEM_PROMPT,
                temperature=0.1,
            )
        except Exception as e:
            errors.append(f"文献 {pubmed_id} 解析失败: {e}")
            extracted = {}

        # 规则层：术语校验
        try:
            validation = terminology.validate_extraction(pubmed_id, extracted)
            if validation["warnings"]:
                logs.append(
                    f"  [术语校验] {len(validation['warnings'])} 条提醒: "
                    + "; ".join(w["message"][:60] for w in validation["warnings"][:3])
                )
        except Exception:
            validation = {"warnings": [], "corrections": []}

        schema = LiteratureSchema(
            pubmed_id=pubmed_id,
            title=title,
            authors=", ".join(paper.get("authors", [])[:5]),
            year=int(paper.get("publication_date", "0")[:4]) if paper.get("publication_date") else 0,
            journal=paper.get("journal", ""),
            doi=paper.get("doi", ""),
            objective=extracted.get("objective", ""),
            method=extracted.get("method", ""),
            target=extracted.get("target", ""),
            biomarker=extracted.get("biomarker", ""),
            sample_size=extracted.get("sample_size", ""),
            model_system=extracted.get("model_system", ""),
            key_findings=extracted.get("key_findings", ""),
            result_value=extracted.get("result_value", ""),
            conclusion=extracted.get("conclusion", ""),
            figures_summary=extracted.get("figures_summary", ""),
            limitations=extracted.get("limitations", ""),
        )

        parsed[pubmed_id] = {
            "structured": schema.to_dict(),
            "paper_info": paper,
            "figures": [],
            "validation": validation,
        }

    logs.append(f"[Parser Worker] 完成。共解析 {len(parsed)} 篇文献")

    return {
        "parsed_papers": parsed,
        "execution_log": logs,
        "errors": state.get("errors", []) + errors,
        "current_step": current_step,
        "next_node": "compare",
    }


# ═══════════════════════════════════════════════════════════════
# Compare Node
# ═══════════════════════════════════════════════════════════════

COMPARE_SYSTEM_PROMPT = """你是一个生物医学文献对比分析专家。你的任务是对比多篇文献，找出其中的共性、差异和研究空白。

请基于每篇文献的提取信息，生成对比分析报告。返回 JSON：
{
  "common_points": ["共性发现1", "共性发现2", ...],
  "contradictions": ["矛盾点1", "矛盾点2", ...],
  "research_gaps": ["研究空白1", "研究空白2", ...],
  "summary": "总体对比总结（2-3段）"
}
"""


def compare_node(state: ResearchState) -> dict:
    """对比节点：跨文献对比分析"""
    parsed = state.get("parsed_papers", {})
    logs = list(state.get("execution_log", []))
    comparison_report = ""

    if len(parsed) < 2:
        logs.append("[Compare Worker] 文献数量不足2篇，跳过对比分析")
        comparison_report = "文献数量不足（少于2篇），无法进行有意义的跨文献对比分析。\n\n建议扩大检索范围或调整关键词。"
        return {
            "comparison_report": comparison_report,
            "execution_log": logs,
            "current_step": "对比分析跳过（文献不足）",
            "next_node": "review_results",
        }

    logs.append(f"[Compare Worker] 开始对比 {len(parsed)} 篇文献")

    structured_summaries = []
    for pubmed_id, data in parsed.items():
        s = data.get("structured", {})
        structured_summaries.append(
            f"文献 [{pubmed_id}]: {s.get('title', 'N/A')}\n"
            f"  目标: {s.get('objective', 'N/A')}\n"
            f"  方法: {s.get('method', 'N/A')}\n"
            f"  靶点: {s.get('target', 'N/A')}\n"
            f"  关键发现: {s.get('key_findings', 'N/A')}\n"
            f"  结论: {s.get('conclusion', 'N/A')}"
        )

    try:
        result = llm.chat_json(
            user_prompt=(
                f"用户研究意图: {state.get('query', '')}\n\n"
                f"需要对比的 {len(parsed)} 篇文献：\n\n"
                + "\n\n---\n\n".join(structured_summaries)
            ),
            system_prompt=COMPARE_SYSTEM_PROMPT,
            temperature=0.2,
        )
    except Exception as e:
        logs.append(f"[Compare Worker] 失败: {e}")
        return {
            "comparison_report": f"对比分析过程出现错误: {e}",
            "execution_log": logs,
            "errors": state.get("errors", []) + [f"对比分析失败: {e}"],
            "current_step": "对比分析失败",
            "next_node": "review_results",
        }

    # 生成 Markdown 报告
    lines = ["# 跨文献对比分析\n"]
    for label, key in [("共同发现", "common_points"), ("矛盾与差异", "contradictions"), ("研究空白", "research_gaps")]:
        items = result.get(key, [])
        if items:
            lines.append(f"## {label}\n")
            for pt in items:
                lines.append(f"- {pt}")
            lines.append("")

    summary = result.get("summary", "")
    if summary:
        lines.append(f"## 总体评估\n\n{summary}\n")

    comparison_report = "\n".join(lines)
    logs.append(f"[Compare Worker] 对比完成")

    return {
        "comparison_report": comparison_report,
        "execution_log": logs,
        "current_step": "对比分析完成",
        "next_node": "review_results",
    }


# ═══════════════════════════════════════════════════════════════
# Review Results Node (HITL 中断点)
# ═══════════════════════════════════════════════════════════════

def review_results_node(state: ResearchState) -> dict:
    """结果审核节点——第二个 HITL 中断点。用户在此处查看结构化提取和对比结果，
    可以选择继续生成报告，或返回修改。
    """
    logs = list(state.get("execution_log", []))
    logs.append("[HITL] 结果审核完成，进入报告生成")
    return {
        "execution_log": logs,
        "next_node": "report",
        "current_step": "审核完成，生成最终报告...",
    }


# ═══════════════════════════════════════════════════════════════
# Report Node
# ═══════════════════════════════════════════════════════════════

REPORT_SYSTEM_PROMPT = """你是一个生物医学文献综述撰写专家。请基于前面的分析结果，生成一份结构清晰的文献概览报告。

报告应包含以下部分（使用 Markdown 格式）：
1. **研究问题概述**：简述用户意图和检索范围
2. **文献概览**：逐篇介绍筛选出的文献（标题、作者、核心发现）
3. **对比分析**：引用 Compare 阶段的对比结果
4. **结论与建议**：总结当前研究现状，给出后续研究建议

要求：
- 每篇文献引用请标注 PubMed ID，格式: [PMID:xxxxx]
- 如果有图表提取结果，使用 ![](path) 格式嵌入
- 报告末尾标注生成时间和数据来源
"""


def report_node(state: ResearchState) -> dict:
    """报告生成节点：汇总所有信息，生成最终 Markdown 报告"""
    logs = list(state.get("execution_log", []))
    logs.append("[Reporter] 正在汇总所有信息，生成最终报告...")
    errors = list(state.get("errors", []))

    # 错误兜底
    if errors and len(errors) >= 3:
        final_report = (
            "# 报告生成失败\n\n执行过程中遇到多个错误：\n\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\n## 已完成步骤\n\n"
            + "\n".join(f"- {log}" for log in state.get("execution_log", []))
        )
        return {
            "final_report": final_report,
            "execution_log": logs,
            "current_step": "完成（有错误）",
            "next_node": "__end__",
        }

    # 构建文献摘要
    paper_summaries = []
    for pubmed_id, data in state.get("parsed_papers", {}).items():
        s = data.get("structured", {})
        paper_summaries.append(
            f"### [{pubmed_id}] {s.get('title', 'N/A')}\n"
            f"- 作者: {s.get('authors', 'N/A')}\n"
            f"- 期刊: {s.get('journal', 'N/A')} ({s.get('year', 'N/A')})\n"
            f"- DOI: {s.get('doi', 'N/A')}\n"
            f"- 靶点: {s.get('target', 'N/A')}\n"
            f"- 方法: {s.get('method', 'N/A')}\n"
            f"- 关键发现: {s.get('key_findings', 'N/A')}\n"
            f"- 结论: {s.get('conclusion', 'N/A')}\n"
        )

    prompt = (
        f"## 用户研究意图\n{state.get('query', '')}\n\n"
        f"## 检索到 {len(paper_summaries)} 篇文献的结构化信息\n\n"
        + "\n".join(paper_summaries)
        + f"\n\n## 对比分析结果\n{state.get('comparison_report', '无')}"
        + f"\n\n请生成最终文献概览报告。"
    )

    try:
        report = llm.chat(
            user_prompt=prompt,
            system_prompt=REPORT_SYSTEM_PROMPT,
            temperature=0.3,
        )
    except Exception as e:
        report = f"# 报告生成失败\n\nLLM 调用出错: {e}"

    report += (
        f"\n\n---\n"
        f"*报告由 Bioinformatics Agent 自动生成 | "
        f"检索文献数: {len(state.get('search_results', []))} | "
        f"筛选文献数: {len(paper_summaries)}*\n"
    )

    logs.append("[Reporter] 最终报告生成完毕")

    return {
        "final_report": report,
        "execution_log": logs,
        "current_step": "完成",
        "next_node": "__end__",
    }
