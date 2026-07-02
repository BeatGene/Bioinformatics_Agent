"""
Executor — 对外暴露的统一入口，委托给 LangGraph StateGraph 执行。

保持与旧 API 的向后兼容：
  execute_research(query, max_papers) → AsyncGenerator[snapshot_dict]

支持多轮对话与人工干预：
  resume_research(thread_id, user_action, ...) → AsyncGenerator[snapshot_dict]
"""
from typing import Any, AsyncGenerator

from backend.agent.graph import (
    run_research as _graph_run,
    resume_research as _graph_resume,
    get_thread_state,
    new_thread_id,
)


async def execute_research(
    query: str,
    max_papers: int = 5,
    thread_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    执行完整研究流程（SSE 流式输出）。

    这是旧 API 的兼容入口，内部委托给 LangGraph StateGraph。
    """
    async for snapshot in _graph_run(
        query=query,
        max_papers=max_papers,
        thread_id=thread_id,
    ):
        yield snapshot


async def resume_research(
    thread_id: str,
    user_action: str,
    feedback: str = "",
    adjusted_query: str = "",
    selected_ids: list[str] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    从 HITL 中断点恢复研究流程。

    Args:
        thread_id: 对话线程 ID
        user_action: "approve" / "retry" / "select"
        feedback: 用户反馈（retry 时说明原因）
        adjusted_query: 调整后的检索式（retry 时使用）
        selected_ids: 用户手动选择的 PMID 列表（select 时使用）
    """
    async for snapshot in _graph_resume(
        thread_id=thread_id,
        user_action=user_action,
        feedback=feedback,
        adjusted_query=adjusted_query,
        selected_ids=selected_ids,
    ):
        yield snapshot
