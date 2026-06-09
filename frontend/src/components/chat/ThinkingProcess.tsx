import { useState, useEffect } from "react";
import { Brain, ChevronDown, CheckCircle2, Loader2 } from "lucide-react";

interface Props {
  steps: string[];
  isStreaming: boolean;
}

export default function ThinkingProcess({ steps, isStreaming }: Props) {
  // 流式中默认展开，结束后默认折叠
  const [open, setOpen] = useState(isStreaming);

  useEffect(() => {
    if (isStreaming) {
      setOpen(true);
    }
  }, [isStreaming]);

  if (steps.length === 0) return null;

  return (
    <div className="thinking-section mb-3">
      {/* 头部 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="thinking-header w-full"
      >
        <Brain className="w-4 h-4 text-purple-500 shrink-0" />
        <span className="text-sm font-medium text-slate-700">思考过程</span>
        <span className="text-xs text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-full">
          {steps.length} 步
        </span>
        <ChevronDown
          className={`w-4 h-4 text-slate-400 ml-auto transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* 步骤列表 */}
      {open && (
        <div className="px-4 pb-3 space-y-1">
          {steps.map((step, i) => {
            const isLast = i === steps.length - 1;
            const isActive = isLast && isStreaming;

            return (
              <div
                key={i}
                className="thinking-step"
                style={{ animationDelay: `${i * 30}ms` }}
              >
                {isActive ? (
                  <Loader2 className="w-3.5 h-3.5 text-purple-500 animate-spin shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                )}
                <span
                  className={`text-sm leading-relaxed ${
                    isActive ? "text-purple-700" : "text-slate-600"
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
