import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Square, Settings2 } from "lucide-react";

interface Props {
  onSend: (query: string, maxPapers: number) => void;
  onAbort: () => void;
  isStreaming: boolean;
}

export default function ChatInput({ onSend, onAbort, isStreaming }: Props) {
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
    <div className="border-t border-slate-100 bg-white px-6 py-4">
      <div className="max-w-3xl mx-auto">
        {/* 设置栏（可折叠） */}
        {showSettings && (
          <div className="flex items-center gap-3 mb-3 px-1">
            <span className="text-xs text-slate-500 shrink-0">最大文献数</span>
            <input
              type="range"
              min={2}
              max={20}
              value={maxPapers}
              onChange={(e) => setMaxPapers(Number(e.target.value))}
              className="flex-1 h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-blue-600"
            />
            <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full min-w-[3rem] text-center">
              {maxPapers} 篇
            </span>
          </div>
        )}

        {/* 输入栏 */}
        <div className="flex items-end gap-3">
          {/* 设置按钮 */}
          <button
            onClick={() => setShowSettings((v) => !v)}
            className={`p-2.5 rounded-xl transition-colors shrink-0 ${
              showSettings
                ? "bg-blue-50 text-blue-600"
                : "bg-slate-50 text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            }`}
            title="设置"
          >
            <Settings2 className="w-4 h-4" />
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
              className="chat-textarea"
            />
          </div>

          {/* 发送 / 停止按钮 */}
          {isStreaming ? (
            <button
              onClick={onAbort}
              className="w-10 h-10 rounded-xl bg-red-500 hover:bg-red-600
                         flex items-center justify-center transition-colors shrink-0"
              title="停止生成"
            >
              <Square className="w-4 h-4 text-white fill-white" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              className="w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-700
                         disabled:opacity-40 disabled:cursor-not-allowed
                         flex items-center justify-center transition-colors shrink-0"
              title="发送"
            >
              <ArrowUp className="w-4 h-4 text-white" />
            </button>
          )}
        </div>

        {/* 底部提示 */}
        <p className="text-[11px] text-slate-400 text-center mt-2">
          Enter 发送，Shift + Enter 换行 · AI 生成内容仅供参考
        </p>
      </div>
    </div>
  );
}
