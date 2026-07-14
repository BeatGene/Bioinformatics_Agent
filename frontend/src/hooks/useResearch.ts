import { useState, useCallback, useRef } from "react";
import type {
  ResearchSnapshot,
  SubTask,
  PaperDetail,
  ResumeResearchPayload,
} from "../types/research";
import { streamResearch, streamResumeResearch } from "../lib/api";

export interface ResearchState {
  loading: boolean;
  threadId: string;
  currentStep: string;
  planSummary: string;
  subTasks: SubTask[];
  executionLog: string[];
  comparisonReport: string;
  finalReport: string;
  errors: string[];
  papers: PaperDetail[];
  candidatePapers: PaperDetail[];
  isPaused: boolean;
  pausePoint: ResearchSnapshot["pause_point"];
  stats: {
    searchResults: number;
    selectedPapers: number;
    parsedPapers: number;
  };
}

const initialState: ResearchState = {
  loading: false,
  threadId: "",
  currentStep: "",
  planSummary: "",
  subTasks: [],
  executionLog: [],
  comparisonReport: "",
  finalReport: "",
  errors: [],
  papers: [],
  candidatePapers: [],
  isPaused: false,
  pausePoint: "",
  stats: { searchResults: 0, selectedPapers: 0, parsedPapers: 0 },
};

function applySnapshot(prev: ResearchState, snapshot: ResearchSnapshot): ResearchState {
  const prevLogLen = prev.executionLog.length;
  const newLogEntries = snapshot.execution_log.slice(prevLogLen);

  return {
    ...prev,
    threadId: snapshot.thread_id,
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
    candidatePapers: snapshot.candidate_papers || [],
    isPaused: snapshot.is_paused,
    pausePoint: snapshot.pause_point,
    stats: {
      searchResults: snapshot.search_results_count,
      selectedPapers: snapshot.selected_papers_count,
      parsedPapers: snapshot.parsed_papers_count,
    },
  };
}

export function useResearch() {
  const [state, setState] = useState<ResearchState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback((query: string, maxPapers: number, conversationId: string | null = null) => {
    // 中断上一个流
    abortRef.current?.abort();
    setState({ ...initialState, loading: true });

    abortRef.current = streamResearch(
      query,
      maxPapers,
      conversationId,
      (snapshot: ResearchSnapshot) => {
        setState((prev) => applySnapshot(prev, snapshot));
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
        setState((prev) => ({
          ...prev,
          loading: false,
          currentStep: prev.isPaused ? prev.currentStep : "完成",
        }));
        abortRef.current = null;
      },
    );
  }, []);

  const resume = useCallback((payload: ResumeResearchPayload) => {
    abortRef.current?.abort();
    setState((prev) => ({
      ...prev,
      loading: true,
      isPaused: false,
      pausePoint: "",
      currentStep: "继续执行...",
    }));

    abortRef.current = streamResumeResearch(
      payload,
      (snapshot: ResearchSnapshot) => {
        setState((prev) => applySnapshot(prev, snapshot));
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
        setState((prev) => ({
          ...prev,
          loading: false,
          currentStep: prev.isPaused ? prev.currentStep : "完成",
        }));
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

  return { ...state, start, resume, abort, reset, getPaperByPmid };
}
