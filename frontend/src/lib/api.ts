import type { ResearchSnapshot } from "../types/research";

/**
 * 通过 SSE 流式获取研究结果。
 * 返回 AbortController 以便调用方随时取消。
 */
export function streamResearch(
  query: string,
  maxPapers: number,
  onSnapshot: (snapshot: ResearchSnapshot) => void,
  onError: (error: string) => void,
  onDone: () => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_papers: maxPapers }),
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
            if (line.startsWith("data: ")) {
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
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err.message : "未知错误");
    }
  })();

  return controller;
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
