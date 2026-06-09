import { useState, useEffect, useCallback, useRef } from "react";
import ChatSidebar from "./components/chat/ChatSidebar";
import ChatView from "./components/chat/ChatView";
import DetailPanel from "./components/DetailPanel";
import { useChat } from "./hooks/useChat";
import { useResearch } from "./hooks/useResearch";
import type { ChatMessage } from "./types/chat";

function genMsgId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export default function App() {
  const {
    activeConversation,
    activeId,
    summaries,
    createConversation,
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
  activeIdRef.current = activeId;

  // 追踪是否正在流式输出
  const isStreamingRef = useRef(false);

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
        errors: research.errors,
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
    updateLastAssistantMessage,
    finalizeConversation,
  ]);

  const handleSend = useCallback(
    (query: string, maxPapers: number) => {
      // 如果没有活跃对话，先创建一个
      let convId = activeId;
      if (!convId) {
        convId = createConversation();
        activeIdRef.current = convId;
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
      research.start(query, maxPapers);
    },
    [activeId, createConversation, addMessage, research],
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
    <div className="h-screen flex bg-white">
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
        onSend={handleSend}
        onAbort={handleAbort}
        onPromptClick={handlePromptClick}
        onPmidClick={handlePmidClick}
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
