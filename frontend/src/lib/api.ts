import type { ResearchSnapshot, ResumeResearchPayload } from "../types/research";

export interface RemoteConversation {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  status: string;
  message_count: number;
}

interface StreamOptions {
  url: string;
  body: unknown;
  onSnapshot: (snapshot: ResearchSnapshot) => void;
  onError: (error: string) => void;
  onDone: () => void;
}

function streamSnapshots({
  url,
  body,
  onSnapshot,
  onError,
  onDone,
}: StreamOptions): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        onError(`服务器错误: ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError("无法读取响应流");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const lines = event.split("\n");
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;

            const data = line.slice(6).trim();
            if (data === "[DONE]") {
              onDone();
              return;
            }

            try {
              const snapshot: ResearchSnapshot = JSON.parse(data);
              onSnapshot(snapshot);
            } catch {
              // 跳过非 JSON 数据
            }
          }
        }
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err.message : "未知错误");
    }
  })();

  return controller;
}

/**
 * 通过 SSE 流式获取研究结果。
 * 返回 AbortController 以便调用方随时取消。
 */
export function streamResearch(
  query: string,
  maxPapers: number,
  conversationId: string | null,
  onSnapshot: (snapshot: ResearchSnapshot) => void,
  onError: (error: string) => void,
  onDone: () => void,
): AbortController {
  return streamSnapshots({
    url: "/api/research",
    body: {
      query,
      max_papers: maxPapers,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    },
    onSnapshot,
    onError,
    onDone,
  });
}

/** 从人工审核暂停点恢复研究流程 */
export function streamResumeResearch(
  payload: ResumeResearchPayload,
  onSnapshot: (snapshot: ResearchSnapshot) => void,
  onError: (error: string) => void,
  onDone: () => void,
): AbortController {
  return streamSnapshots({
    url: "/api/research/resume",
    body: payload,
    onSnapshot,
    onError,
    onDone,
  });
}

/** 创建后端对话，用于让研究记录和消息进入后端数据库 */
export async function createRemoteConversation(title: string): Promise<RemoteConversation> {
  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    throw new Error(`创建后端对话失败: ${res.status}`);
  }

  return res.json();
}

/** 健康检查 */
export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch("/api/health");
    return res.ok;
  } catch {
    return false;
  }
}
