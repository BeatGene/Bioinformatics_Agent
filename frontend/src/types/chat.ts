import type { PaperDetail, ResearchSnapshot } from "./research";

/** 对话中的单条消息 */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  /** 助手消息：执行日志条目（对应 execution_log） */
  thinkingSteps?: string[];
  /** 助手消息：解析后的论文列表 */
  papers?: PaperDetail[];
  /** 助手消息：检索审核用完整候选文献 */
  candidatePapers?: PaperDetail[];
  /** 助手消息：错误信息 */
  errors?: string[];
  /** 助手消息：跨文献对比报告 */
  comparisonReport?: string;
  /** 后端 LangGraph thread_id，用于 HITL resume */
  threadId?: string;
  /** 后端流程是否暂停等待人工审核 */
  isPaused?: boolean;
  /** 已提交的审核结果快照，只展示内容，不再允许交互 */
  reviewReadOnly?: boolean;
  /** 暂停点：检索审核或结果审核 */
  pausePoint?: ResearchSnapshot["pause_point"];
  /** SSE 流式更新中 */
  isStreaming?: boolean;
}

/** 一个对话 */
export interface Conversation {
  id: string;
  /** 后端 Conversation.id；本地空会话可能还没有 */
  serverConversationId?: string;
  /** 自动取自首条用户消息 */
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

/** 侧边栏列表用的轻量摘要 */
export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: number;
  messageCount: number;
}
