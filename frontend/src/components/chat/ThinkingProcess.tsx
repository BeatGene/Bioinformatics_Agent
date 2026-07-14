import { useState } from "react";
import { Brain, ChevronDown, CheckCircle2, Loader2 } from "lucide-react";

interface Props {
  steps: string[];
  isStreaming: boolean;
}

export default function ThinkingProcess({ steps, isStreaming }: Props) {
  const [open, setOpen] = useState(false);
  const visible = isStreaming || open;

  if (steps.length === 0) return null;

  return (
    <div className="thinking-section mb-3">
      {/* 头部 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="thinking-header w-full text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-cyan-700"
        aria-expanded={visible}
      >
        <Brain className="h-4 w-4 shrink-0 text-cyan-700" aria-hidden="true" />
        <span className="text-sm font-semibold text-[var(--ink)]">证据处理过程</span>
        <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 text-xs text-[var(--ink-muted)]">
          {steps.length} 步
        </span>
        <ChevronDown
          className={`ml-auto h-4 w-4 text-[var(--ink-subtle)] transition-transform duration-200 ${
            visible ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* 步骤列表 */}
      {visible && (
        <div className="px-4 pb-3 space-y-1">
          {steps.map((step, i) => {
            const isLast = i === steps.length - 1;
            const isActive = isLast && isStreaming;

            return (
              <div key={i} className="thinking-step">
                {isActive ? (
                  <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-cyan-700" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" aria-hidden="true" />
                )}
                <span
                  className={`text-sm leading-relaxed ${
                    isActive ? "text-cyan-800" : "text-[var(--ink-muted)]"
                  }`}
                >
                  {step.replace(/^\[.*?\]\s*/, "")}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
