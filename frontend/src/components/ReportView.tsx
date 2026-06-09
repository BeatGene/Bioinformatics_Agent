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

/** 自定义 Markdown 渲染，PMID 标签可点击 */
function MarkdownRenderer({
  content,
  onPmidClick,
}: {
  content: string;
  onPmidClick?: (pmid: string) => void;
}) {
  // 预处理：将 [PMID:xxxxx] 替换为 Markdown 链接（由自定义 a 组件渲染为可点击标签）
  const processed = useMemo(() => {
    return content.replace(
      /\[PMID:(\d+)\]/g,
      (_match, pmid: string) =>
        `[PMID: ${pmid}](https://pubmed.ncbi.nlm.nih.gov/${pmid}/)`,
    );
  }, [content]);

  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeKatex]}
      components={{
        a: ({ href, children, ...props }) => {
          // PMID 标签特殊处理
          if (href?.includes("pubmed.ncbi.nlm.nih.gov")) {
            const pmid = href.split("/").pop() || "";
            return (
              <span
                className="pmid-tag cursor-pointer"
                onClick={(e) => {
                  e.preventDefault();
                  onPmidClick?.(pmid);
                }}
              >
                PMID: {pmid}
              </span>
            );
          }
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

export default function ReportView({ report, loading, onPmidClick }: Props) {
  if (!report && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
        <FileText className="w-16 h-16 text-slate-200" />
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
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        <p className="text-sm text-slate-500">正在生成报告...</p>
      </div>
    );
  }

  return (
    <div className="report-content px-1">
      <MarkdownRenderer content={report} onPmidClick={onPmidClick} />
      {loading && (
        <div className="flex items-center gap-2 text-blue-500 mt-4 pb-8">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">更新中...</span>
        </div>
      )}
    </div>
  );
}
