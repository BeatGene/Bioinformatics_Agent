"""
LangGraph State 定义 —— Agent 执行过程中的共享状态。
支持多轮对话、人工干预（HITL）、checkpoint 持久化。
"""
from typing import Annotated, Any, TypedDict
from langgraph.graph.message import add_messages


class ResearchState(TypedDict):
    """研究 Agent 的全局状态（兼容 LangGraph StateGraph）"""

    # ── 会话标识 ──
    thread_id: str                      # 对话线程 ID（LangGraph checkpoint key）
    messages: Annotated[list, add_messages]  # 多轮对话消息历史

    # ── 用户输入 ──
    query: str                          # 当前研究意图（可能是原始查询或修正后的查询）
    max_papers: int                     # 最大检索文献数

    # ── Planner 输出 ──
    plan_summary: str                   # 规划摘要

    # ── 检索结果 ──
    search_results: list[dict[str, Any]]    # PubMed 检索返回的文献列表
    selected_papers: list[dict[str, Any]]   # 筛选后的文献

    # ── 人工干预字段 (HITL) ──
    user_action: str                    # 用户在前端的选择: "approve" | "retry" | "select" | ""
    user_approved_search: bool          # 用户是否批准检索结果（HITL 中断点1）
    user_selected_ids: list[str]        # 用户手动勾选的 PMID 列表
    user_feedback: str                  # 用户反馈指令（如 "重新搜索，关键词换成XX"）
    user_adjusted_query: str            # 用户调整后的检索式

    # ── 解析结果 ──
    parsed_papers: dict[str, dict[str, Any]]    # {pubmed_id: {structured, paper_info, validation}}
    pdf_available: dict[str, str]               # {pubmed_id: pdf_path or ""}

    # ── 对比分析 ──
    comparison_report: str              # 对比报告 Markdown

    # ── 最终输出 ──
    final_report: str                   # 最终 Markdown 报告

    # ── 执行日志与状态 ──
    execution_log: list[str]            # 普通 list，各节点从已有日志继承后追加（避免 add_messages 在 HITL 循环中无限累积）
    errors: list[str]
    current_step: str                   # 当前执行步骤描述
    next_node: str                      # 下一步路由目标（条件边使用）
