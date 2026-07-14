import { useMemo } from "react";
import ReactFlow, {
  type Node,
  type Edge,
  Background,
  Controls,
  MarkerType,
} from "reactflow";
import { Circle, CircleCheck, FileSearch, FileText, LoaderCircle, Scale, Search, Workflow, type LucideIcon } from "lucide-react";
import type { SubTask } from "../types/research";

interface Props {
  subTasks: SubTask[];
}

const TYPE_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; border: string; icon: LucideIcon }
> = {
  search: { label: "检索", color: "#0e7490", bg: "#ecfeff", border: "#a5f3fc", icon: Search },
  parse: { label: "解析", color: "#0e7490", bg: "#ecfeff", border: "#a5f3fc", icon: FileSearch },
  compare: { label: "对比", color: "#0e7490", bg: "#ecfeff", border: "#a5f3fc", icon: Scale },
  report: { label: "报告", color: "#0e7490", bg: "#ecfeff", border: "#a5f3fc", icon: FileText },
};

const STATUS_STYLE: Record<string, string> = {
  pending: "#e2e8f0",
  running: "#3b82f6",
  done: "#22c55e",
  failed: "#ef4444",
};

const NODE_W = 220;
const LEVEL_GAP_Y = 140;

/** 拓扑排序 → 按层级分组，水平分布 */
function computeLayout(tasks: SubTask[]) {
  const taskMap = new Map(tasks.map((t) => [t.id, t]));

  // BFS 计算深度
  const depth = new Map<string, number>();
  const roots = tasks.filter((t) => t.depends_on.length === 0);

  for (const root of roots) {
    const queue = [{ id: root.id, d: 0 }];
    while (queue.length > 0) {
      const { id, d } = queue.shift()!;
      if (!depth.has(id) || depth.get(id)! < d) {
        depth.set(id, d);
      }
      // 找所有依赖此节点的任务
      for (const t of tasks) {
        if (t.depends_on.includes(id)) {
          queue.push({ id: t.id, d: d + 1 });
        }
      }
    }
  }

  // 按深度分组
  const levels = new Map<number, SubTask[]>();
  for (const task of tasks) {
    const d = depth.get(task.id) ?? 0;
    if (!levels.has(d)) levels.set(d, []);
    levels.get(d)!.push(task);
  }

  // 计算位置
  const maxLevel = Math.max(...levels.keys(), 0);
  const nodes: Node[] = [];
  const positionMap = new Map<string, { x: number; y: number }>();

  for (let lvl = 0; lvl <= maxLevel; lvl++) {
    const levelTasks = levels.get(lvl) || [];
    const totalWidth = levelTasks.length * NODE_W + (levelTasks.length - 1) * 40;
    const startX = -totalWidth / 2;

    levelTasks.forEach((task, i) => {
      const x = startX + i * (NODE_W + 40);
      const y = lvl * LEVEL_GAP_Y;
      positionMap.set(task.id, { x, y });
    });
  }

  // 构建节点和边
  const edgeArr: Edge[] = [];

  for (const task of tasks) {
    const config = TYPE_CONFIG[task.type] || TYPE_CONFIG.search;
    const TaskIcon = config.icon;
    const borderColor = STATUS_STYLE[task.status] || STATUS_STYLE.pending;
    const isRunning = task.status === "running";
    const isDone = task.status === "done";
    const pos = positionMap.get(task.id)!;

    nodes.push({
      id: task.id,
      position: { x: pos.x, y: pos.y },
      type: "default",
      data: {
        label: (
          <div
            className={`
              px-4 py-3 rounded-xl text-left border-2 transition-colors duration-200
              ${isRunning ? "" : ""}
            `}
            style={{
              width: NODE_W,
              borderColor,
              backgroundColor: config.bg,
            }}
          >
            <span
              className="inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded"
              style={{
                color: config.color,
                backgroundColor: `${config.color}18`,
              }}
            >
              <TaskIcon className="h-3 w-3" aria-hidden="true" />
              {config.label}
            </span>
            <p className="text-xs text-slate-700 mt-1.5 leading-snug line-clamp-2">
              {task.description}
            </p>
            <span
              className="mt-1.5 flex items-center gap-1 text-[11px] font-medium"
              style={{ color: borderColor }}
            >
              {isRunning ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : isDone ? <CircleCheck className="h-3 w-3" aria-hidden="true" /> : <Circle className="h-3 w-3" aria-hidden="true" />}
              {isRunning ? "执行中" : isDone ? "已完成" : "等待中"}
            </span>
          </div>
        ),
      },
      style: { background: "transparent", border: "none", padding: 0 },
    });

    // 边
    task.depends_on.forEach((depId) => {
      if (taskMap.has(depId)) {
        edgeArr.push({
          id: `${depId}-${task.id}`,
          source: depId,
          target: task.id,
          animated: task.status === "running",
          style: {
            stroke: task.status === "done" ? "#22c55e" : "#cbd5e1",
            strokeWidth: 2.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: task.status === "done" ? "#22c55e" : "#cbd5e1",
          },
        });
      }
    });
  }

  return { nodes, edgeArr };
}

export default function DAGFlow({ subTasks }: Props) {
  const { nodes, edgeArr } = useMemo(
    () => (subTasks.length > 0 ? computeLayout(subTasks) : { nodes: [], edgeArr: [] }),
    [subTasks],
  );

  if (subTasks.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-slate-400 bg-white rounded-xl border border-slate-200">
        <div className="text-center">
          <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center">
            <Workflow className="h-5 w-5 text-slate-400" aria-hidden="true" />
          </div>
          等待任务规划...
        </div>
      </div>
    );
  }

  return (
    <div className="h-[500px] w-full rounded-xl overflow-hidden border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edgeArr}
        fitView
        fitViewOptions={{ padding: 0.4, maxZoom: 1.5 }}
        minZoom={0.3}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#f1f5f9" gap={20} size={1} />
        <Controls showZoom showFitView={false} showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
