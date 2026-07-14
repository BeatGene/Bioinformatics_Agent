import { useState, useCallback, useEffect, useMemo } from "react";
import type { ChatMessage, Conversation, ConversationSummary } from "../types/chat";

const STORAGE_KEY = "bio-agent-conversations";

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // 损坏时清空
    localStorage.removeItem(STORAGE_KEY);
  }
  return [];
}

function saveConversations(convs: Conversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
  } catch {
    // localStorage 满时忽略
  }
}

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(null);

  // 持久化到 localStorage
  useEffect(() => {
    const timeoutId = window.setTimeout(() => saveConversations(conversations), 250);
    return () => window.clearTimeout(timeoutId);
  }, [conversations]);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [activeId, conversations],
  );

  const summaries: ConversationSummary[] = useMemo(
    () =>
      conversations
        .map((conversation) => ({
          id: conversation.id,
          title: conversation.title,
          updatedAt: conversation.updatedAt,
          messageCount: conversation.messages.length,
        }))
        .sort((a, b) => b.updatedAt - a.updatedAt),
    [conversations],
  );

  const createConversation = useCallback((title?: string, serverConversationId?: string): string => {
    const id = genId();
    const now = Date.now();
    const newConv: Conversation = {
      id,
      serverConversationId,
      title: title || "新对话",
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(id);
    return id;
  }, []);

  const setServerConversationId = useCallback((convId: string, serverConversationId: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, serverConversationId } : c)),
    );
  }, []);

  const selectConversation = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(() => {
          const remaining = conversations.filter((c) => c.id !== id);
          return remaining.length > 0 ? remaining[0].id : null;
        });
      }
    },
    [activeId, conversations],
  );

  const addMessage = useCallback(
    (msg: ChatMessage, convId?: string) => {
      const targetId = convId ?? activeId;
      if (!targetId) return;
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== targetId) return c;
          const updatedMessages = [...c.messages, msg];
          // 如果是第一条用户消息，用它作标题
          const title =
            c.messages.length === 0 && msg.role === "user"
              ? msg.content.slice(0, 30) + (msg.content.length > 30 ? "..." : "")
              : c.title;
          return { ...c, messages: updatedMessages, title, updatedAt: Date.now() };
        }),
      );
    },
    [activeId],
  );

  const updateLastAssistantMessage = useCallback(
    (patch: Partial<ChatMessage>, convId?: string) => {
      const targetId = convId ?? activeId;
      if (!targetId) return;
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== targetId) return c;
          const msgs = [...c.messages];
          // 找到最后一条助手消息
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === "assistant") {
              msgs[i] = { ...msgs[i], ...patch };
              break;
            }
          }
          return { ...c, messages: msgs, updatedAt: Date.now() };
        }),
      );
    },
    [activeId],
  );

  const finalizeConversation = useCallback(
    (convId?: string) => {
      const targetId = convId ?? activeId;
      if (!targetId) return;
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== targetId) return c;
          const msgs = c.messages.map((m) =>
            m.role === "assistant" && m.isStreaming ? { ...m, isStreaming: false } : m,
          );
          return { ...c, messages: msgs, updatedAt: Date.now() };
        }),
      );
    },
    [activeId],
  );

  return {
    conversations,
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
  };
}
