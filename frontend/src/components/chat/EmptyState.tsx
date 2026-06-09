import { Dna, Search, FlaskConical, BarChart3 } from "lucide-react";

interface Props {
  onPromptClick: (prompt: string) => void;
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

export default function EmptyState({ onPromptClick }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
      {/* Logo */}
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-6 shadow-lg shadow-blue-500/20">
        <Dna className="w-8 h-8 text-white" />
      </div>

      {/* 标题 */}
      <h1 className="text-2xl font-semibold text-slate-800 mb-2">
        Bioinformatics Agent
      </h1>
      <p className="text-sm text-slate-500 mb-10">
        AI 驱动的生物医学文献智能分析 — 输入研究问题，自动检索、解析并生成报告
      </p>

      {/* 示例问题卡片 */}
      <div className="w-full max-w-2xl space-y-3">
        {EXAMPLE_PROMPTS.map((item, i) => {
          const Icon = item.icon;
          return (
            <button
              key={i}
              onClick={() => onPromptClick(item.text)}
              className="w-full text-left px-5 py-4 rounded-xl border border-slate-200
                         bg-white hover:bg-slate-50 hover:border-slate-300
                         transition-all group"
            >
              <div className="flex items-start gap-3">
                <Icon className="w-4 h-4 text-slate-400 group-hover:text-blue-500 shrink-0 mt-0.5 transition-colors" />
                <span className="text-sm text-slate-600 group-hover:text-slate-800 leading-relaxed transition-colors">
                  {item.text}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
