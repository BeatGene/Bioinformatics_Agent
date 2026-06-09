import { useState, useCallback, useRef } from "react";
import type { ResearchSnapshot, SubTask, PaperDetail } from "../types/research";
import { streamResearch } from "../lib/api";

export interface ResearchState {
  loading: boolean;
  currentStep: string;
  planSummary: string;
  subTasks: SubTask[];
  executionLog: string[];
  comparisonReport: string;
  finalReport: string;
  errors: string[];
  papers: PaperDetail[];
  stats: {
    searchResults: number;
    selectedPapers: number;
    parsedPapers: number;
  };
}

const initialState: ResearchState = {
  loading: false,
  currentStep: "",
  planSummary: "",
  subTasks: [],
  executionLog: [],
  comparisonReport: "",
  finalReport: "",
  errors: [],
  papers: [],
  stats: { searchResults: 0, selectedPapers: 0, parsedPapers: 0 },
};

export function useResearch() {
  const [state, setState] = useState<ResearchState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback((query: string, maxPapers: number) => {
    // 中断上一个流
    abortRef.current?.abort();
    setState({ ...initialState, loading: true });

    abortRef.current = streamResearch(
      query,
      maxPapers,
      (snapshot: ResearchSnapshot) => {
        setState((prev) => {
          // 增量追加 execution_log（只追加新条目）
          const prevLogLen = prev.executionLog.length;
          const newLogEntries = snapshot.execution_log.slice(prevLogLen);

          return {
            ...prev,
            currentStep: snapshot.current_step,
            planSummary: snapshot.plan_summary,
            subTasks: snapshot.sub_tasks,
            executionLog:
              newLogEntries.length > 0
                ? [...prev.executionLog, ...newLogEntries]
                : prev.executionLog,
            comparisonReport: snapshot.comparison_report,
            finalReport: snapshot.final_report,
            errors: snapshot.errors,
            papers: snapshot.papers || [],
            stats: {
              searchResults: snapshot.search_results_count,
              selectedPapers: snapshot.selected_papers_count,
              parsedPapers: snapshot.parsed_papers_count,
            },
          };
        });
      },
      (error: string) => {
        setState((prev) => ({
          ...prev,
          loading: false,
          errors: [...prev.errors, error],
          currentStep: "执行出错",
        }));
        abortRef.current = null;
      },
      () => {
        setState((prev) => ({ ...prev, loading: false, currentStep: "完成" }));
        abortRef.current = null;
      },
    );
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState((prev) => ({ ...prev, loading: false, currentStep: "已中止" }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(initialState);
  }, []);

  const getPaperByPmid = useCallback(
    (pmid: string) => state.papers.find((p) => p.pubmed_id === pmid) || null,
    [state.papers],
  );

  return { ...state, start, abort, reset, getPaperByPmid };
}
