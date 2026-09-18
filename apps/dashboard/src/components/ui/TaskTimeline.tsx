import React from "react";
import type { DAGNode } from "@nexus/types";
import { StatusBadge } from "./StatusBadge";

interface TaskTimelineProps {
  nodes: DAGNode[];
  activeNodeId?: string;
  onSelectNode?: (node: DAGNode) => void;
}

export function TaskTimeline({ nodes, activeNodeId, onSelectNode }: TaskTimelineProps) {
  if (!nodes || nodes.length === 0) {
    return (
      <div className="text-center p-6 text-xs text-slate-500 font-mono">
        No DAG nodes registered in this task
      </div>
    );
  }

  return (
    <div className="space-y-3 font-mono">
      {nodes.map((node, index) => {
        const isSelected = node.id === activeNodeId;
        const isLast = index === nodes.length - 1;

        return (
          <div key={node.id} className="relative flex items-start gap-3">
            {/* Step indicator & connector line */}
            <div className="flex flex-col items-center">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border transition-colors ${
                  node.status === "completed"
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
                    : node.status === "executing"
                    ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/40 animate-pulse"
                    : node.status === "awaiting_approval"
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/40"
                    : node.status === "failed"
                    ? "bg-rose-500/20 text-rose-400 border-rose-500/40"
                    : "bg-slate-800 text-slate-400 border-white/10"
                }`}
              >
                {index + 1}
              </div>
              {!isLast && (
                <div
                  className={`w-0.5 h-8 my-1 ${
                    node.status === "completed" ? "bg-emerald-500/40" : "bg-white/10"
                  }`}
                />
              )}
            </div>

            {/* Node Card */}
            <div
              onClick={() => onSelectNode && onSelectNode(node)}
              className={`flex-1 p-3.5 rounded-xl border transition-all cursor-pointer ${
                isSelected
                  ? "bg-slate-800/90 border-cyan-500/50 shadow-lg shadow-cyan-500/5"
                  : "bg-slate-900/60 border-white/5 hover:border-white/15"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="font-semibold text-xs text-white truncate">
                  {node.name}
                </span>
                <StatusBadge status={node.status} />
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
                <span>Agent: <strong className="text-slate-300">{node.agent}</strong></span>
                {node.tool && (
                  <span>Tool: <code className="text-cyan-400">{node.tool}</code></span>
                )}
                {node.dependencies.length > 0 && (
                  <span className="text-slate-500">
                    Depends on: {node.dependencies.join(", ")}
                  </span>
                )}
              </div>

              {node.error && (
                <div className="mt-2 p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px]">
                  {node.error}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
