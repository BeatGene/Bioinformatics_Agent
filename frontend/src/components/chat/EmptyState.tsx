import type { ReactNode } from "react";
import { ArrowUpRight, Dna, Search, FlaskConical, BarChart3, ShieldCheck } from "lucide-react";

interface Props {
  onPromptClick: (prompt: string) => void;
  children: ReactNode;
}

const EXAMPLE_PROMPTS = [
  {
    icon: Search,
    text: "对比近三年针对 EGFR 靶点的 NSCLC 临床研究中 PD-1 抑制剂的疗效与安全性数据",
  },
  {
    icon: FlaskConical,
    text: "CRISPR-Cas9 基因编辑技术在遗传性疾病治疗中的最新临床进展",
  },
  {
    icon: BarChart3,
    text: "PD-1/PD-L1 抑制剂联合化疗对比单药治疗在晚期肺癌中的疗效 Meta 分析",
  },
];

export default function EmptyState({ onPromptClick, children }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-5 py-8 sm:px-10 lg:px-16">
      <div className="mx-auto flex min-h-full max-w-5xl flex-col justify-center py-8">
        <div className="mb-9 max-w-3xl">
          <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-700 text-white shadow-[0_6px_8px_oklch(0.47_0.13_222_/_0.2)]">
            <Dna className="h-6 w-6" aria-hidden="true" />
          </div>
          <p className="mb-3 text-sm font-semibold tracking-[0.01em] text-cyan-800">研究工作台</p>
          <h1 className="max-w-2xl text-3xl font-semibold tracking-[-0.025em] text-slate-950 text-balance sm:text-4xl">
            把研究问题变成可追溯的证据链。
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-7 text-slate-600 text-pretty">
            描述临床或基础研究问题。系统检索 PubMed，筛选相关证据，并将结论组织成可核对的研究报告。
          </p>
        </div>

        <section className="max-w-4xl" aria-labelledby="research-question-heading">
          <div className="mb-3 flex items-baseline justify-between gap-4">
            <h2 id="research-question-heading" className="text-sm font-semibold text-slate-800">你的研究问题</h2>
            <span className="hidden text-xs text-slate-500 sm:inline">可调整检索文献数量</span>
          </div>
          {children}
        </section>

        <section className="mt-10 max-w-4xl" aria-labelledby="examples-heading">
          <div className="mb-3 flex items-baseline justify-between gap-4">
            <h2 id="examples-heading" className="text-sm font-semibold text-slate-800">从一个研究任务开始</h2>
            <span className="hidden text-xs text-slate-500 sm:inline">点击即可立即开始分析</span>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
        {EXAMPLE_PROMPTS.map((item, i) => {
          const Icon = item.icon;
          return (
            <button
              key={i}
              onClick={() => onPromptClick(item.text)}
              className="group flex min-h-38 flex-col rounded-xl border border-slate-200 bg-white p-4 text-left shadow-[0_1px_2px_oklch(0.2_0.03_255_/_0.05)] transition-[border-color,background-color,transform] duration-200 ease-out hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
            >
              <div className="flex items-start justify-between gap-3">
                <Icon className="h-4 w-4 shrink-0 text-cyan-700" aria-hidden="true" />
                <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300 transition-colors group-hover:text-cyan-700" aria-hidden="true" />
              </div>
              <span className="mt-7 text-sm leading-6 text-slate-700">{item.text}</span>
            </button>
          );
        })}
          </div>
        </section>

        <div className="mt-9 flex max-w-4xl items-start gap-2.5 border-t border-slate-200 pt-5 text-xs leading-5 text-slate-600">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan-700" aria-hidden="true" />
          <p><span className="font-semibold text-slate-700">证据处理过程可回溯。</span> 检索、筛选、文献解析与报告生成均会在对话中保留，便于核对每一步依据。</p>
        </div>
      </div>
    </div>
  );
}
