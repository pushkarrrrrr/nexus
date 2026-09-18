"use client";

import React, { useState } from "react";
import { mockDAGs } from "../../src/mockData/mockTasks";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { TaskTimeline } from "../../src/components/ui/TaskTimeline";
import type { DAGNode, TaskDAG } from "@nexus/types";
import { Network, CheckCircle2, Clock } from "lucide-react";

export default function TasksPage() {
  const [selectedDAG, setSelectedDAG] = useState<TaskDAG>(mockDAGs[0]);
  const [selectedNode, setSelectedNode] = useState<DAGNode>(mockDAGs[0].nodes[1]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Tasks &amp; Topological DAGs</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Deterministic Directed Acyclic Graphs synthesized by the Planning Agent
          </p>
        </div>

        <div className="flex items-center gap-2">
          {mockDAGs.map((dag) => (
            <button
              key={dag.dag_id}
              onClick={() => {
                setSelectedDAG(dag);
                setSelectedNode(dag.nodes[0]);
              }}
              className={`px-3 py-1.5 rounded-lg font-mono text-xs transition-all border ${
                selectedDAG.dag_id === dag.dag_id
                  ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400"
                  : "bg-slate-900 border-white/10 text-slate-400 hover:text-white"
              }`}
            >
              {dag.dag_id}
            </button>
          ))}
        </div>
      </div>

      {/* Grid: Left Column DAG Timeline, Right Column Node Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: DAG Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <Card
            title={
              <div className="flex items-center gap-2">
                <Network size={16} className="text-cyan-400" />
                <span>DAG Plan: {selectedDAG.dag_id}</span>
              </div>
            }
            subtitle={selectedDAG.goal}
            badge={<StatusBadge status={selectedDAG.status} />}
          >
            <div className="mt-4">
              <TaskTimeline
                nodes={selectedDAG.nodes}
                activeNodeId={selectedNode?.id}
                onSelectNode={(node) => setSelectedNode(node)}
              />
            </div>
          </Card>
        </div>

        {/* Right Column: Node Step Inspector */}
        <div>
          <Card
            title={selectedNode ? selectedNode.name : "Step Inspector"}
            subtitle={selectedNode ? `Node ID: ${selectedNode.id}` : "Select a step to inspect"}
            badge={selectedNode && <StatusBadge status={selectedNode.status} />}
          >
            {selectedNode ? (
              <div className="space-y-4 font-mono text-xs">
                <div className="space-y-2 border-b border-white/10 pb-3">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Agent:</span>
                    <span className="text-slate-200 font-bold">{selectedNode.agent}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Designated Tool:</span>
                    <span className="text-cyan-400">{selectedNode.tool || "None"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Dependencies:</span>
                    <span className="text-slate-300">
                      {selectedNode.dependencies.length > 0
                        ? selectedNode.dependencies.join(", ")
                        : "None (Root node)"}
                    </span>
                  </div>
                </div>

                {/* Input Payload */}
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1">
                    Input Parameters
                  </span>
                  <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                    {JSON.stringify(selectedNode.input || {}, null, 2)}
                  </pre>
                </div>

                {/* Observation / Result */}
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1">
                    Result / Observation
                  </span>
                  <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                    {JSON.stringify(selectedNode.result || { status: "Awaiting execution" }, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-center p-6 text-xs text-slate-500 font-mono">
                Click any node in the timeline to inspect inputs and results.
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
