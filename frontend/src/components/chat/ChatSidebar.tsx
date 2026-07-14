import { Dna, Plus, MessageSquare, Trash2, LogIn } from "lucide-react";
import type { ConversationSummary } from "../../types/chat";

interface Props {
  summaries: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function ChatSidebar({
  summaries,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  return (
    <aside className="hidden w-[272px] shrink-0 flex-col border-r border-slate-800 bg-slate-950 md:flex" aria-label="对话导航">
      {/* 品牌区 */}
      <div className="px-5 pb-5 pt-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500 text-slate-950">
          <Dna className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-[-0.01em] text-white leading-none">BioAgent</h1>
          <p className="mt-1 text-[11px] leading-none text-slate-400">文献智能分析</p>
        </div>
      </div>

      {/* 新建对话按钮 */}
      <div className="px-4 mb-4">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 rounded-lg bg-cyan-500 px-3 py-2.5 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300"
        >
          <Plus className="w-4 h-4" aria-hidden="true" />
          新建对话
        </button>
      </div>

      {/* 对话历史列表 */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <p className="px-2 pb-2 text-[11px] font-medium text-slate-500">对话记录</p>
        {summaries.length === 0 && (
          <p className="text-xs text-slate-500 text-center py-8">暂无对话记录</p>
        )}
        <ul className="space-y-0.5">
        {summaries.map((conv) => (
          <li key={conv.id} className="group relative">
            <button
            onClick={() => onSelect(conv.id)}
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 pr-9 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-cyan-300 ${
              activeId === conv.id
                ? "bg-white/10 text-white"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
            <span className="text-sm truncate flex-1">{conv.title}</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="absolute right-1 top-1/2 size-10 -translate-y-1/2 rounded text-slate-500 opacity-0 hover:bg-white/10 hover:text-red-300 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-cyan-300 group-hover:opacity-100 transition-opacity"
              aria-label={`删除对话：${conv.title}`}
            >
              <Trash2 className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" aria-hidden="true" />
            </button>
          </li>
        ))}
        </ul>
      </div>

      {/* 底部：登录占位 */}
      <div className="px-4 py-4 border-t border-slate-800">
        <button className="w-full flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:bg-slate-900 hover:text-slate-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 transition-colors">
          <LogIn className="w-4 h-4" aria-hidden="true" />
          登录 / 注册
        </button>
      </div>
    </aside>
  );
}
