import { Dna, Loader2, AlertCircle } from "lucide-react";
import type { ChatMessage } from "../../types/chat";
import ThinkingProcess from "./ThinkingProcess";
import ReportView from "../ReportView";

interface Props {
  message: ChatMessage;
  onPmidClick?: (pmid: string) => void;
}

export default function AssistantMessage({ message, onPmidClick }: Props) {
  const hasReport = !!message.content;
  const hasThinking = (message.thinkingSteps?.length ?? 0) > 0;
  const hasErrors = (message.errors?.length ?? 0) > 0;

  return (
    <div className="flex gap-3 py-4">
      {/* 头像 */}
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center shrink-0">
        <Dna className="w-4 h-4 text-white" />
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
          <div className="flex items-center gap-2 text-slate-400 py-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">正在生成报告...</span>
          </div>
        )}

        {/* 最终报告 */}
        {hasReport && (
          <div className="report-content">
            <ReportView
              report={message.content}
              loading={!!message.isStreaming}
              onPmidClick={onPmidClick}
            />
          </div>
        )}

        {/* 错误信息 */}
        {hasErrors && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl">
            {message.errors!.map((err, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-red-600">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{err}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
