import type { ChatMessage } from "../../types/chat";
import type { ResumeResearchPayload } from "../../types/research";
import EmptyState from "./EmptyState";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import { Dna, Plus } from "lucide-react";

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  onNew: () => void;
  onSend: (query: string, maxPapers: number) => void;
  onAbort: () => void;
  onPromptClick: (prompt: string) => void;
  onPmidClick?: (pmid: string) => void;
  onResume?: (payload: ResumeResearchPayload) => void;
}

export default function ChatView({
  messages,
  isStreaming,
  onNew,
  onSend,
  onAbort,
  onPromptClick,
  onPmidClick,
  onResume,
}: Props) {
  const isEmpty = messages.length === 0;

  return (
    <main id="main-content" className="flex-1 flex flex-col min-w-0 bg-[var(--canvas)]" aria-label="生物医学文献研究工作区" tabIndex={-1}>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-500 text-slate-950">
            <Dna className="h-4 w-4" aria-hidden="true" />
          </span>
          BioAgent
        </div>
        <button
          type="button"
          onClick={onNew}
          className="inline-flex items-center gap-1.5 rounded-md bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          新对话
        </button>
      </header>
      {isEmpty ? (
        <EmptyState onPromptClick={onPromptClick}>
          <ChatInput
            onSend={onSend}
            onAbort={onAbort}
            isStreaming={isStreaming}
            variant="home"
          />
        </EmptyState>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          onPmidClick={onPmidClick}
          onResume={onResume}
        />
      )}

      {!isEmpty && (
        <ChatInput
          onSend={onSend}
          onAbort={onAbort}
          isStreaming={isStreaming}
        />
      )}
    </main>
  );
}
