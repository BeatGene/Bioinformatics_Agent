import { lazy, Suspense } from "react";
import { Dna, Loader2, AlertCircle } from "lucide-react";
import type { ChatMessage } from "../../types/chat";
import type { ResumeResearchPayload } from "../../types/research";
import ThinkingProcess from "./ThinkingProcess";
import ReviewControls from "./ReviewControls";

const ReportView = lazy(() => import("../ReportView"));

interface Props {
  message: ChatMessage;
  onPmidClick?: (pmid: string) => void;
  onResume?: (payload: ResumeResearchPayload) => void;
}

export default function AssistantMessage({ message, onPmidClick, onResume }: Props) {
  const hasReport = !!message.content;
  const hasThinking = (message.thinkingSteps?.length ?? 0) > 0;
  const hasErrors = (message.errors?.length ?? 0) > 0;
  const showReview =
    (!!message.isPaused || !!message.reviewReadOnly) &&
    !!message.threadId &&
    !!message.pausePoint &&
    (!!onResume || !!message.reviewReadOnly);

  return (
      <div className="flex gap-3 py-5">
      {/* 头像 */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-cyan-700 text-white">
        <Dna className="h-4 w-4" aria-hidden="true" />
      </div>

      {/* 内容 */}
      <div className="message-assistant">
        {/* 思考过程 */}
        {hasThinking && (
          <ThinkingProcess
            steps={message.thinkingSteps!}
            isStreaming={!!message.isStreaming}
          />
        )}

        {/* 加载状态（流式中且无报告） */}
        {message.isStreaming && !hasReport && (
          <div className="flex items-center gap-2 py-2 text-[var(--ink-muted)]" role="status" aria-live="polite">
            <Loader2 className="h-4 w-4 animate-spin text-cyan-700" aria-hidden="true" />
            <span className="text-sm">正在处理研究证据…</span>
          </div>
        )}

        {showReview && (
          <ReviewControls
            threadId={message.threadId!}
            pausePoint={message.pausePoint!}
            papers={message.papers || []}
            candidatePapers={message.candidatePapers || []}
            comparisonReport={message.comparisonReport}
            disabled={!!message.isStreaming}
            readOnly={!!message.reviewReadOnly}
            onResume={onResume}
          />
        )}

        {/* 最终报告 */}
        {hasReport && (
          <Suspense
            fallback={
              <div className="flex items-center gap-2 py-3 text-sm text-[var(--ink-muted)]" role="status">
                <Loader2 className="h-4 w-4 animate-spin text-cyan-700" aria-hidden="true" />
                正在载入报告阅读器…
              </div>
            }
          >
            <div className="report-content">
              <ReportView
                report={message.content}
                loading={!!message.isStreaming}
                onPmidClick={onPmidClick}
              />
            </div>
          </Suspense>
        )}

        {/* 错误信息 */}
        {hasErrors && (
          <div className="mt-3 border border-[color:var(--danger)]/25 bg-rose-50 p-3 text-[color:var(--danger)]" role="alert">
            {message.errors!.map((err, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{err}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
