import { X, ExternalLink, BookOpen, Users, Calendar } from "lucide-react";

interface PaperDetail {
  pubmed_id: string;
  title: string;
  abstract: string;
  authors: string[];
  journal: string;
  publication_date: string;
  doi: string;
  url: string;
  objective?: string;
  method?: string;
  target?: string;
  key_findings?: string;
  conclusion?: string;
}

interface Props {
  paper: PaperDetail | null;
  onClose: () => void;
}

export default function DetailPanel({ paper, onClose }: Props) {
  if (!paper) return null;

  return (
    <aside className="fixed inset-0 z-30 flex w-full flex-col overflow-y-auto border-l border-[var(--line)] bg-[var(--surface)] pb-[env(safe-area-inset-bottom)] md:static md:w-100 md:shrink-0" aria-label="文献详情">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--line)] bg-[var(--surface)] px-5 py-4">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-cyan-700" aria-hidden="true" />
          <span className="text-sm font-semibold text-[var(--ink)]">文献详情</span>
        </div>
        <button
          onClick={onClose}
          className="size-10 rounded-md text-[var(--ink-muted)] hover:bg-[var(--surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
          aria-label="关闭文献详情"
        >
          <X className="w-4 h-4 text-slate-400" aria-hidden="true" />
        </button>
      </div>

      <div className="space-y-6 p-5">
        {/* 标题 */}
          <h2 className="text-lg font-semibold leading-snug text-[var(--ink)] text-balance">
          {paper.title}
        </h2>

        {/* 元信息 */}
        <div className="space-y-2 text-xs leading-5 text-[var(--ink-muted)]">
          <div className="flex items-center gap-2">
            <Users className="w-3.5 h-3.5" aria-hidden="true" />
            <span>{paper.authors?.slice(0, 3).join(", ") || "N/A"}
              {(paper.authors?.length || 0) > 3 ? " et al." : ""}</span>
          </div>
          <div className="flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5" aria-hidden="true" />
            <span>{paper.journal || "N/A"} · {paper.publication_date || "N/A"}</span>
          </div>
          {paper.doi && (
            <div className="break-all text-[11px] text-[var(--ink-subtle)]">
              DOI: {paper.doi}
            </div>
          )}
        </div>

        {/* PubMed 链接 */}
        <a
          href={paper.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-[var(--line-strong)] px-3 py-1.5 text-xs font-semibold text-cyan-800 transition-colors hover:border-cyan-700 hover:bg-[var(--accent-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
        >
          <ExternalLink className="w-3 h-3" aria-hidden="true" />
          在 PubMed 中查看
        </a>

        {/* 结构化信息 */}
        {paper.objective && (
          <InfoBlock label="研究目标" content={paper.objective} />
        )}
        {paper.method && (
          <InfoBlock label="方法" content={paper.method} />
        )}
        {paper.target && (
          <InfoBlock label="靶点 / 对象" content={paper.target} />
        )}
        {paper.key_findings && (
          <InfoBlock label="关键发现" content={paper.key_findings} />
        )}
        {paper.conclusion && (
          <InfoBlock label="结论" content={paper.conclusion} />
        )}

        {/* 摘要 */}
        {paper.abstract && (
          <div>
            <h3 className="mb-2 text-xs font-semibold text-[var(--ink-muted)]">
              摘要
            </h3>
            <p className="text-sm leading-7 text-[var(--ink-muted)]">
              {paper.abstract.slice(0, 500)}
              {paper.abstract.length > 500 ? "…" : ""}
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}

function InfoBlock({ label, content }: { label: string; content: string }) {
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-semibold text-[var(--ink-muted)]">
        {label}
      </h3>
      <p className="text-sm leading-7 text-[var(--ink)]">{content}</p>
    </div>
  );
}
