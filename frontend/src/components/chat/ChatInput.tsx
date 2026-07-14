import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Square, Settings2 } from "lucide-react";

interface Props {
  onSend: (query: string, maxPapers: number) => void;
  onAbort: () => void;
  isStreaming: boolean;
  variant?: "docked" | "home";
}

export default function ChatInput({
  onSend,
  onAbort,
  isStreaming,
  variant = "docked",
}: Props) {
  const [query, setQuery] = useState("");
  const [maxPapers, setMaxPapers] = useState(5);
  const [showSettings, setShowSettings] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整 textarea 高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [query]);

  const handleSend = useCallback(() => {
    if (!query.trim() || isStreaming) return;
    onSend(query.trim(), maxPapers);
    setQuery("");
    // 重置 textarea 高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [query, maxPapers, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = query.trim().length > 0 && !isStreaming;

  return (
    <div
      className={
        variant === "home"
          ? "w-full"
          : "border-t border-[var(--line)] bg-[var(--surface)] px-5 py-4 sm:px-8"
      }
    >
      <div className={variant === "home" ? "mx-auto max-w-4xl" : "mx-auto max-w-3xl"}>
        {/* 设置栏（可折叠） */}
        {showSettings && (
          <div id="research-settings" className="flex items-center gap-3 mb-3 px-1">
            <label htmlFor="max-papers" className="text-xs font-medium text-slate-600 shrink-0">最大文献数</label>
            <input
              type="range"
              min={2}
              max={20}
              value={maxPapers}
              onChange={(e) => setMaxPapers(Number(e.target.value))}
              id="max-papers"
              className="flex-1 h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-cyan-700"
            />
            <span className="text-xs font-semibold text-cyan-800 bg-cyan-50 px-2 py-0.5 rounded-full min-w-[3rem] text-center">
              {maxPapers} 篇
            </span>
          </div>
        )}

        {/* 输入栏 */}
        <div className={variant === "home" ? "flex items-end gap-3 rounded-xl border border-[var(--line-strong)] bg-[var(--surface)] p-2 shadow-sm focus-within:border-cyan-700" : "flex items-end gap-3"}>
          {/* 设置按钮 */}
          <button
            onClick={() => setShowSettings((v) => !v)}
            className={`size-10 rounded-lg transition-colors shrink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700 ${
              showSettings
                ? "bg-cyan-50 text-cyan-700"
                : "bg-slate-50 text-slate-500 hover:text-slate-700 hover:bg-slate-100"
            }`}
            aria-label="调整检索设置"
            aria-expanded={showSettings}
            aria-controls="research-settings"
          >
            <Settings2 className="w-4 h-4" aria-hidden="true" />
          </button>

          {/* Textarea */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的生物医学研究问题..."
              rows={1}
              disabled={isStreaming}
              aria-label="生物医学研究问题"
              className={`chat-textarea ${variant === "home" ? "border-0 bg-transparent px-2 py-2.5 shadow-none focus:border-0 focus:ring-0" : ""}`}
            />
          </div>

          {/* 发送 / 停止按钮 */}
          {isStreaming ? (
            <button
              onClick={onAbort}
              className="w-10 h-10 rounded-lg bg-rose-600 hover:bg-rose-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700
                         flex items-center justify-center transition-colors shrink-0"
              aria-label="停止生成"
            >
              <Square className="w-4 h-4 text-white fill-white" aria-hidden="true" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              className="w-10 h-10 rounded-lg bg-cyan-700 hover:bg-cyan-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700
                         disabled:opacity-40 disabled:cursor-not-allowed
                         flex items-center justify-center transition-colors shrink-0"
              aria-label="发送研究问题"
            >
              <ArrowUp className="w-4 h-4 text-white" aria-hidden="true" />
            </button>
          )}
        </div>

        {/* 底部提示 */}
        <p className={`text-[11px] text-slate-500 ${variant === "home" ? "mt-3 px-1" : "mt-2 text-center"}`}>
          Enter 发送，Shift + Enter 换行 · 结果附带 PubMed 来源，供研究决策参考
        </p>
      </div>
    </div>
  );
}
