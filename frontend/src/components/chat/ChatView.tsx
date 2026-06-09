import type { ChatMessage } from "../../types/chat";
import EmptyState from "./EmptyState";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSend: (query: string, maxPapers: number) => void;
  onAbort: () => void;
  onPromptClick: (prompt: string) => void;
  onPmidClick?: (pmid: string) => void;
}

export default function ChatView({
  messages,
  isStreaming,
  onSend,
  onAbort,
  onPromptClick,
  onPmidClick,
}: Props) {
  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-white">
      {isEmpty ? (
        <EmptyState onPromptClick={onPromptClick} />
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          onPmidClick={onPmidClick}
        />
      )}

      <ChatInput
        onSend={onSend}
        onAbort={onAbort}
        isStreaming={isStreaming}
      />
    </div>
  );
}
