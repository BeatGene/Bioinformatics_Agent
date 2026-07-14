import { useMemo, useState } from "react";
import { Check, RotateCcw, ListChecks, Send, MessageSquareText } from "lucide-react";
import type { PaperDetail, ResearchSnapshot, ResumeResearchPayload } from "../../types/research";

interface Props {
  threadId: string;
  pausePoint: ResearchSnapshot["pause_point"];
  papers: PaperDetail[];
  candidatePapers?: PaperDetail[];
  comparisonReport?: string;
  disabled?: boolean;
  readOnly?: boolean;
  onResume?: (payload: ResumeResearchPayload) => void;
}

interface PaperSummary {
  purpose: string;
  method: string;
  finding: string;
}

function splitSentences(text: string): string[] {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return [];

  const sentences = normalized.match(/[^.!?。！？]+[.!?。！？]+/g) || [];
  if (sentences.length > 0) return sentences.map((sentence) => sentence.trim());

  return normalized
    .split(/;|；/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function findSentence(sentences: string[], patterns: RegExp[]): string {
  return (
    sentences.find((sentence) =>
      patterns.some((pattern) => pattern.test(sentence)),
    ) || ""
  );
}

function shorten(text: string, maxLength = 260): string {
  if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength).trim()}…`;
}

function summarizePaper(paper: PaperDetail): PaperSummary {
  const sentences = splitSentences(paper.abstract);
  if (sentences.length === 0) {
    return {
      purpose: "暂无摘要信息，建议根据标题、期刊和 PMID 判断是否纳入。",
      method: "",
      finding: "",
    };
  }

  const purpose =
    findSentence(sentences, [
      /\b(this study|we aimed|we sought|we investigated|we evaluated|objective|aim|purpose|background)\b/i,
      /研究|旨在|目的|探讨|评估/,
    ]) || sentences[0];

  const method =
    findSentence(sentences, [
      /\b(retrospective|prospective|cohort|randomized|trial|meta-analysis|systematic review|patients were|included|enrolled|methods?)\b/i,
      /回顾性|前瞻性|队列|随机|试验|系统综述|荟萃|纳入|患者/,
    ]) || sentences[1] || "";

  const finding =
    findSentence(sentences, [
      /\b(results?|findings?|showed|demonstrated|suggest|conclusion|in conclusion|median|significant|improved|associated)\b/i,
      /结果|发现|显示|提示|结论|显著|改善|相关/,
    ]) || sentences[sentences.length - 1] || "";

  return {
    purpose: shorten(purpose),
    method: method && method !== purpose ? shorten(method) : "",
    finding:
      finding && finding !== purpose && finding !== method
        ? shorten(finding)
        : "",
  };
}

export default function ReviewControls({
  threadId,
  pausePoint,
  papers,
  candidatePapers = [],
  comparisonReport,
  disabled = false,
  readOnly = false,
  onResume,
}: Props) {
  const [feedback, setFeedback] = useState("");
  const [adjustedQuery, setAdjustedQuery] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const reviewPapers = candidatePapers.length > 0 ? candidatePapers : papers;
  const [selectedIds, setSelectedIds] = useState<string[]>(() => {
    const defaults = reviewPapers
      .filter((paper) => paper.is_default_selected)
      .map((paper) => paper.pubmed_id);
    return defaults.length > 0
      ? defaults
      : reviewPapers.slice(0, 5).map((paper) => paper.pubmed_id);
  });

  const title = pausePoint === "review_results" ? "结果审核" : "检索结果审核";
  const canSelect = pausePoint === "review_search" && reviewPapers.length > 0;
  const hasSelection = selectedIds.length > 0;

  const selectedSummary = useMemo(() => {
    if (!canSelect) return "";
    return `已选择 ${selectedIds.length}/${reviewPapers.length} 篇`;
  }, [canSelect, reviewPapers.length, selectedIds.length]);

  const submitApprove = () => {
    onResume?.({ thread_id: threadId, user_action: "approve" });
  };

  const submitRetry = () => {
    onResume?.({
      thread_id: threadId,
      user_action: "retry",
      feedback: feedback.trim(),
      adjusted_query: adjustedQuery.trim(),
    });
  };

  const submitRevise = () => {
    onResume?.({
      thread_id: threadId,
      user_action: "revise",
      feedback: feedback.trim(),
    });
  };

  const submitSelection = () => {
    onResume?.({
      thread_id: threadId,
      user_action: "select",
      selected_ids: selectedIds,
    });
  };

  const togglePaper = (pmid: string) => {
    setSelectedIds((prev) =>
      prev.includes(pmid) ? prev.filter((id) => id !== pmid) : [...prev, pmid],
    );
  };

  return (
    <div className="review-panel mt-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-[var(--ink)]">{title}</div>
          <div className="mt-1 max-w-2xl text-xs leading-5 text-[var(--ink-muted)]">
            {readOnly
              ? "已提交，保留本次审核内容。"
              : pausePoint === "review_results"
              ? "检查结构化提取和对比结果；满意后生成最终报告，或对分析提出修改意见。"
              : "检查候选文献后继续；如检索方向不对，可以调整检索式重新搜索。"}
          </div>
        </div>
        {selectedSummary && (
          <span className="rounded bg-[var(--surface-muted)] px-2 py-1 text-xs text-[var(--ink-muted)]">
            {selectedSummary}
          </span>
        )}
      </div>

      {canSelect && (
        <div className="mt-3 space-y-2">
          {reviewPapers.map((paper, index) => {
            const isDefault = !!paper.is_default_selected;
            const summary = summarizePaper(paper);

            return (
            <label
              key={paper.pubmed_id}
              className="review-paper-row"
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(paper.pubmed_id)}
                onChange={() => togglePaper(paper.pubmed_id)}
                disabled={disabled || readOnly}
                className="mt-1"
              />
              <span className="min-w-0">
                <span className="flex items-start gap-2 min-w-0">
                  <span className="text-xs font-semibold text-slate-400 w-6 shrink-0">
                    #{index + 1}
                  </span>
                  <span className="block text-sm font-medium text-slate-800 leading-snug">
                    {paper.title || `PMID ${paper.pubmed_id}`}
                  </span>
                </span>
                <span className="block text-xs text-slate-500 truncate pl-8">
                  PMID {paper.pubmed_id}
                  {paper.journal ? ` · ${paper.journal}` : ""}
                  {paper.publication_date ? ` · ${paper.publication_date}` : ""}
                </span>
                <span className="block pl-8 mt-2 space-y-1.5">
                  <span className="block text-sm text-slate-600 leading-relaxed">
                    <span className="font-medium text-slate-700">研究内容：</span>
                    {summary.purpose}
                  </span>
                  {summary.method && (
                    <span className="block text-sm text-slate-600 leading-relaxed">
                      <span className="font-medium text-slate-700">方法/对象：</span>
                      {summary.method}
                    </span>
                  )}
                  {summary.finding && (
                    <span className="block text-sm text-slate-600 leading-relaxed">
                      <span className="font-medium text-slate-700">主要发现：</span>
                      {summary.finding}
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-2 pl-8 mt-2">
                  {isDefault && (
                    <span className="review-badge review-badge-primary">推荐</span>
                  )}
                </span>
              </span>
            </label>
            );
          })}
        </div>
      )}

      {pausePoint === "review_results" && comparisonReport && (
        <div className="mt-3 max-h-44 overflow-y-auto rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 whitespace-pre-wrap">
          {comparisonReport}
        </div>
      )}

      {!readOnly && (
      <>
      <div className="mt-3 grid gap-2">
        <button
          type="button"
          onClick={submitApprove}
          disabled={disabled}
          className="review-button review-button-primary w-full justify-center"
          title="审核通过，继续下一步"
        >
          <Check className="w-4 h-4" aria-hidden="true" />
          继续
        </button>

        {canSelect && (
          <button
            type="button"
            onClick={submitSelection}
            disabled={disabled || !hasSelection}
            className="review-button w-full justify-center"
            title="仅使用勾选文献继续"
          >
            <ListChecks className="w-4 h-4" aria-hidden="true" />
            按选择继续
          </button>
        )}
      </div>

      <div className="mt-3 border-t border-slate-200 pt-3 grid gap-2">
        {!showFeedback && (
          <button
            type="button"
            onClick={() => setShowFeedback(true)}
            disabled={disabled}
            className="review-button w-full justify-center"
            title={pausePoint === "review_results" ? "对当前分析提出修改意见" : "调整检索式重新搜索"}
          >
            {pausePoint === "review_results" ? (
              <MessageSquareText className="w-4 h-4" aria-hidden="true" />
            ) : (
              <RotateCcw className="w-4 h-4" aria-hidden="true" />
            )}
            {pausePoint === "review_results" ? "修改分析" : "调整检索"}
          </button>
        )}

        {showFeedback && (
          <div className="grid gap-2">
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={
                pausePoint === "review_results"
                  ? "输入你希望 AI 修改分析的方向，例如：重点比较疗效终点和耐药机制，减少背景介绍。"
                  : "输入为什么要重新检索，例如：结果太泛，重点限定 EGFR-TKI resistance in NSCLC。"
              }
              disabled={disabled}
              aria-label="审核反馈"
              className="review-input min-h-16"
            />
            {pausePoint === "review_search" && (
              <input
                value={adjustedQuery}
                onChange={(e) => setAdjustedQuery(e.target.value)}
                placeholder="调整后的 PubMed 检索式或关键词，用于重新搜索"
                disabled={disabled}
                aria-label="调整后的 PubMed 检索式或关键词"
                className="review-input"
              />
            )}
          </div>
        )}

        {showFeedback && pausePoint === "review_search" && (
          <button
            type="button"
            onClick={submitRetry}
            disabled={disabled || (!feedback.trim() && !adjustedQuery.trim())}
            className="review-button w-full justify-center"
            title="根据反馈重新检索"
          >
            <Send className="w-4 h-4" aria-hidden="true" />
            重新搜索
          </button>
        )}

        {showFeedback && pausePoint === "review_results" && (
          <button
            type="button"
            onClick={submitRevise}
            disabled={disabled || !feedback.trim()}
            className="review-button w-full justify-center"
            title="根据反馈重新生成对比分析"
          >
            <Send className="w-4 h-4" aria-hidden="true" />
            提交修改
          </button>
        )}
      </div>
      </>
      )}
    </div>
  );
}
