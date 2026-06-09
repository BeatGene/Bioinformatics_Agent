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
    <aside className="w-[260px] shrink-0 bg-slate-900 flex flex-col">
      {/* 品牌区 */}
      <div className="px-4 py-5 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <Dna className="w-4 h-4 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-white leading-none">BioAgent</h1>
          <p className="text-[11px] text-slate-400 leading-none mt-0.5">文献智能分析</p>
        </div>
      </div>

      {/* 新建对话按钮 */}
      <div className="px-3 mb-2">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
                     border border-slate-700 text-slate-300 text-sm
                     hover:bg-slate-800 hover:text-white transition-colors"
        >
          <Plus className="w-4 h-4" />
          新建对话
        </button>
      </div>

      {/* 对话历史列表 */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {summaries.length === 0 && (
          <p className="text-xs text-slate-500 text-center py-8">暂无对话记录</p>
        )}
        {summaries.map((conv) => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`group flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
              activeId === conv.id
                ? "bg-white/10 text-white"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5 shrink-0" />
            <span className="text-sm truncate flex-1">{conv.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 transition-all"
              title="删除对话"
            >
              <Trash2 className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" />
            </button>
          </div>
        ))}
      </div>

      {/* 底部：登录占位 */}
      <div className="px-3 py-4 border-t border-slate-800">
        <button className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-slate-400 text-sm hover:bg-slate-800 hover:text-slate-200 transition-colors">
          <LogIn className="w-4 h-4" />
          登录 / 注册
        </button>
      </div>
    </aside>
  );
}
