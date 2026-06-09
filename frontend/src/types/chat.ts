import type { PaperDetail } from "./research";

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
  /** 助手消息：错误信息 */
  errors?: string[];
  /** SSE 流式更新中 */
  isStreaming?: boolean;
}

/** 一个对话 */
export interface Conversation {
  id: string;
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
