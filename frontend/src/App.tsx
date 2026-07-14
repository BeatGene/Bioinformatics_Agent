import { useState, useEffect, useCallback, useRef } from "react";
import ChatSidebar from "./components/chat/ChatSidebar";
import ChatView from "./components/chat/ChatView";
import DetailPanel from "./components/DetailPanel";
import { useChat } from "./hooks/useChat";
import { useResearch } from "./hooks/useResearch";
import type { ChatMessage } from "./types/chat";
import type { ResumeResearchPayload } from "./types/research";
import { createRemoteConversation } from "./lib/api";

function genMsgId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function describeResumeAction(payload: ResumeResearchPayload): string {
  if (payload.user_action === "select") {
    const count = payload.selected_ids?.length ?? 0;
    return `按选择继续：解析已勾选的 ${count} 篇文献。`;
  }

  if (payload.user_action === "retry") {
    const parts = [
      payload.feedback ? `反馈：${payload.feedback}` : "",
      payload.adjusted_query ? `调整检索式：${payload.adjusted_query}` : "",
    ].filter(Boolean);
    return `调整检索并重新搜索${parts.length > 0 ? `\n\n${parts.join("\n")}` : ""}`;
  }

  if (payload.user_action === "revise") {
    return `修改分析：${payload.feedback || "请根据反馈重新分析。"}`;
  }

  return "继续下一步。";
}

export default function App() {
  const {
    activeConversation,
    activeId,
    summaries,
    createConversation,
    setServerConversationId,
    selectConversation,
    deleteConversation,
    addMessage,
    updateLastAssistantMessage,
    finalizeConversation,
  } = useChat();

  const research = useResearch();
  const [selectedPmid, setSelectedPmid] = useState<string | null>(null);

  // 用 ref 追踪当前活跃对话 ID（解决 useEffect 闭包问题）
  const activeIdRef = useRef<string | null>(activeId);

  // 追踪是否正在流式输出
  const isStreamingRef = useRef(false);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  // 将 research 状态同步到聊天消息
  useEffect(() => {
    const convId = activeIdRef.current;
    if (!convId) return;
    if (!research.loading && !research.finalReport && research.executionLog.length === 0) return;

    const wasStreaming = isStreamingRef.current;
    isStreamingRef.current = research.loading;

    updateLastAssistantMessage(
      {
        thinkingSteps: research.executionLog,
        content: research.finalReport,
        papers: research.papers,
        candidatePapers: research.candidatePapers,
        errors: research.errors,
        comparisonReport: research.comparisonReport,
        threadId: research.threadId,
        isPaused: research.isPaused,
        pausePoint: research.pausePoint,
        isStreaming: research.loading,
      },
      convId,
    );

    // 流式结束时保存对话
    if (wasStreaming && !research.loading) {
      finalizeConversation(convId);
    }
  }, [
    research.loading,
    research.executionLog,
    research.finalReport,
    research.errors,
    research.papers,
    research.candidatePapers,
    research.comparisonReport,
    research.threadId,
    research.isPaused,
    research.pausePoint,
    updateLastAssistantMessage,
    finalizeConversation,
  ]);

  const handleSend = useCallback(
    async (query: string, maxPapers: number) => {
      // 如果没有活跃对话，先创建一个
      let convId = activeId;
      let serverConvId = activeConversation?.serverConversationId ?? null;

      if (!convId) {
        try {
          const remote = await createRemoteConversation(query.slice(0, 80));
          serverConvId = remote.id;
          convId = createConversation(undefined, remote.id);
        } catch {
          convId = createConversation();
        }
        activeIdRef.current = convId;
      } else if (!serverConvId) {
        try {
          const remote = await createRemoteConversation(query.slice(0, 80));
          serverConvId = remote.id;
          setServerConversationId(convId, remote.id);
        } catch {
          serverConvId = null;
        }
      }

      // 添加用户消息
      const userMsg: ChatMessage = {
        id: genMsgId(),
        role: "user",
        content: query,
        timestamp: Date.now(),
      };
      addMessage(userMsg, convId);

      // 添加空的助手消息占位
      const assistantMsg: ChatMessage = {
        id: genMsgId(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        thinkingSteps: [],
        papers: [],
        errors: [],
        isStreaming: true,
      };
      addMessage(assistantMsg, convId);

      // 关闭详情面板
      setSelectedPmid(null);

      // 启动研究
      isStreamingRef.current = true;
      research.start(query, maxPapers, serverConvId);
    },
    [
      activeId,
      activeConversation?.serverConversationId,
      createConversation,
      setServerConversationId,
      addMessage,
      research,
    ],
  );

  const handleResume = useCallback(
    (payload: ResumeResearchPayload) => {
      const convId = activeIdRef.current;
      if (!convId) return;

      updateLastAssistantMessage(
        {
          isPaused: false,
          isStreaming: false,
          reviewReadOnly: true,
          ...(payload.user_action === "select"
            ? {
                candidatePapers:
                  activeConversation?.messages
                    .filter((message) => message.role === "assistant")
                    .at(-1)
                    ?.candidatePapers?.map((paper) => ({
                      ...paper,
                      is_default_selected: payload.selected_ids?.includes(paper.pubmed_id) ?? false,
                    })) || [],
              }
            : {}),
        },
        convId,
      );

      const userMsg: ChatMessage = {
        id: genMsgId(),
        role: "user",
        content: describeResumeAction(payload),
        timestamp: Date.now(),
      };
      addMessage(userMsg, convId);

      const assistantMsg: ChatMessage = {
        id: genMsgId(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        thinkingSteps: [],
        papers: [],
        errors: [],
        isStreaming: true,
      };
      addMessage(assistantMsg, convId);

      isStreamingRef.current = true;
      research.resume(payload);
    },
    [activeConversation?.messages, addMessage, research, updateLastAssistantMessage],
  );

  const handleAbort = useCallback(() => {
    research.abort();
    isStreamingRef.current = false;
    finalizeConversation();
  }, [research, finalizeConversation]);

  const handleNew = useCallback(() => {
    // 如果正在流式中，先中止
    if (research.loading) {
      research.abort();
      isStreamingRef.current = false;
      finalizeConversation();
    }
    createConversation();
  }, [research, createConversation, finalizeConversation]);

  const handleSelect = useCallback(
    (id: string) => {
      // 如果正在流式中，先中止
      if (research.loading) {
        research.abort();
        isStreamingRef.current = false;
        finalizeConversation();
      }
      selectConversation(id);
      setSelectedPmid(null);
    },
    [research, selectConversation, finalizeConversation],
  );

  const handleDelete = useCallback(
    (id: string) => {
      if (!window.confirm("确定要删除这条对话吗？此操作无法撤销。")) return;
      // 如果删除的是当前正在流式的对话，先中止
      if (id === activeId && research.loading) {
        research.abort();
        isStreamingRef.current = false;
      }
      deleteConversation(id);
    },
    [activeId, research, deleteConversation],
  );

  const handlePromptClick = useCallback(
    (prompt: string) => {
      handleSend(prompt, 5);
    },
    [handleSend],
  );

  const handlePmidClick = useCallback((pmid: string) => {
    setSelectedPmid((prev) => (prev === pmid ? null : pmid));
  }, []);

  const messages = activeConversation?.messages ?? [];

  return (
    <div className="flex h-dvh bg-[var(--canvas)] text-[var(--ink)]">
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-50 rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white focus:not-sr-only focus:outline-2 focus:outline-offset-2 focus:outline-cyan-800"
      >
        跳至研究工作区
      </a>
      <ChatSidebar
        summaries={summaries}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
      />

      <ChatView
        messages={messages}
        isStreaming={research.loading}
        onNew={handleNew}
        onSend={handleSend}
        onAbort={handleAbort}
        onPromptClick={handlePromptClick}
        onPmidClick={handlePmidClick}
        onResume={handleResume}
      />

      {selectedPmid && (
        <DetailPanel
          paper={research.getPaperByPmid(selectedPmid)}
          onClose={() => setSelectedPmid(null)}
        />
      )}
    </div>
  );
}
