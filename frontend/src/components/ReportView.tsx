import { useMemo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import { FileText, Loader2 } from "lucide-react";

interface Props {
  report: string;
  loading: boolean;
  onPmidClick?: (pmid: string) => void;
}

/** 统一报告中的 PubMed 引用为直接可读的纯文本。 */
function MarkdownRenderer({ content }: { content: string }) {
  const processed = useMemo(() => {
    return content
      // 有编号的各种写法，统一为直接显示的 PMID 文本。
      .replace(/(?:\[|【|（)?PMID\s*[:：]\s*(\d+)(?:\]|】|）)?/gi, "PMID: $1")
      // 对比分析常用的 [12345678] 也直接写出 PMID 前缀。
      .replace(/\[(\d{7,9})\](?!\()/g, "PMID: $1")
      // 模型没有给出编号时，不保留无意义的空标签。
      .replace(/^[ \t]*PMID\s*[:：][ \t]*\r?\n?/gim, "");
  }, [content]);

  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeKatex]}
      components={{
        h1: ({ children }) => <h1 className="report-title">{children}</h1>,
        h2: ({ children }) => <h2 className="report-section-title">{children}</h2>,
        table: ({ children }) => (
          <div className="report-table-wrap" tabIndex={0} aria-label="报告数据表，可横向滚动">
            <table>{children}</table>
          </div>
        ),
        a: ({ href, children, ...props }) => {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          );
        },
      }}
    >
      {processed}
    </Markdown>
  );
}

export default function ReportView({ report, loading }: Props) {
  if (!report && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
        <FileText className="w-16 h-16 text-slate-200" aria-hidden="true" />
        <div className="text-center">
          <p className="text-lg font-medium text-slate-500">准备开始研究</p>
          <p className="text-sm mt-1">
            在左侧输入你的生物医学研究问题，AI Agent 将自动检索、解析、对比文献并生成报告。
          </p>
        </div>
      </div>
    );
  }

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <Loader2 className="w-8 h-8 text-cyan-700 animate-spin" aria-hidden="true" />
        <p className="text-sm text-[var(--ink-muted)]" role="status">正在生成报告…</p>
      </div>
    );
  }

  return (
    <article className="report-shell" aria-label="研究报告">
      <div className="report-content">
        <MarkdownRenderer content={report} />
      </div>
      {loading && (
        <div className="mt-4 flex items-center gap-2 pb-8 text-cyan-700" role="status" aria-live="polite">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
          <span className="text-sm">更新中…</span>
        </div>
      )}
    </article>
  );
}
