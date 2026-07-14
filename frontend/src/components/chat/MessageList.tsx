import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../types/chat";
import type { ResumeResearchPayload } from "../../types/research";
import UserMessage from "./UserMessage";
import AssistantMessage from "./AssistantMessage";

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  onPmidClick?: (pmid: string) => void;
  onResume?: (payload: ResumeResearchPayload) => void;
}

export default function MessageList({
  messages,
  isStreaming,
  onPmidClick,
  onResume,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部（仅在用户未手动上滚时）
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 判断用户是否在底部附近（100px 以内）
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 100;

    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "auto" });
    }
  }, [messages, isStreaming]);

  return (
    <div ref={containerRef} className="message-list flex-1 px-5 sm:px-8">
      <div className="mx-auto max-w-[860px]">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <UserMessage key={msg.id} message={msg} />
          ) : (
            <AssistantMessage
              key={msg.id}
              message={msg}
              onPmidClick={onPmidClick}
              onResume={onResume}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
