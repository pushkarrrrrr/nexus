"use client";

import React, { useState } from "react";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { Target, CheckCircle2, Clock, Plus } from "lucide-react";

interface GoalItem {
  id: string;
  title: string;
  category: string;
  progress: number;
  status: "executing" | "completed" | "pending";
  milestones: { title: string; completed: boolean }[];
  target_date: string;
}

const mockGoals: GoalItem[] = [
  {
    id: "goal_01",
    title: "Implement Production-Grade Security & Policy Kernel",
    category: "Architecture",
    progress: 75,
    status: "executing",
    target_date: "Phase 2 / Capstone",
    milestones: [
      { title: "Define 4-tier risk matrix (LOW, MEDIUM, HIGH, CRITICAL)", completed: true },
      { title: "Pre-execution file snapshot & SHA-256 diff engine", completed: true },
      { title: "Diff-based interactive approval modal", completed: true },
      { title: "Automated rollback / undo handler integration", completed: false },
    ],
  },
  {
    id: "goal_02",
    title: "Dual Surface Ambient Overlay & Global Hotkey Protocol",
    category: "Client Surfaces",
    progress: 100,
    status: "completed",
    target_date: "Phase 1 / Verified",
    milestones: [
      { title: "Tauri-ready React desktop HUD shell", completed: true },
      { title: "Simulated global hotkey listener (Cmd+Shift+Space)", completed: true },
      { title: "WebSocket real-time event multiplexing with Dashboard", completed: true },
    ],
  },
  {
    id: "goal_03",
    title: "Personal Knowledge Base & Local Vector Indexing",
    category: "Intelligence",
    progress: 30,
    status: "pending",
    target_date: "Phase 4",
    milestones: [
      { title: "Document chunking & local embedding models", completed: true },
      { title: "Hybrid search (BM25 + Cosine Similarity)", completed: false },
      { title: "Local filesystem folder auto-sync", completed: false },
    ],
  },
];

export default function GoalsPage() {
  const [goals] = useState<GoalItem[]>(mockGoals);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Autonomous Goals</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            High-level mission objectives decomposed into milestone DAGs
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {goals.map((goal) => (
          <Card
            key={goal.id}
            title={
              <div className="flex items-center gap-2">
                <Target size={16} className="text-cyan-400" />
                <span className="truncate">{goal.title}</span>
              </div>
            }
            badge={<StatusBadge status={goal.status} />}
            subtitle={`Target: ${goal.target_date} • Category: ${goal.category}`}
          >
            {/* Progress Bar */}
            <div className="my-3 space-y-1 font-mono text-xs">
              <div className="flex justify-between text-slate-400 text-[11px]">
                <span>Progress</span>
                <span className="text-white font-bold">{goal.progress}%</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    goal.status === "completed"
                      ? "bg-emerald-400"
                      : "bg-gradient-to-r from-cyan-400 to-blue-500"
                  }`}
                  style={{ width: `${goal.progress}%` }}
                />
              </div>
            </div>

            {/* Milestones List */}
            <div className="mt-4 space-y-2 border-t border-white/5 pt-3 font-mono text-xs">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                Decomposed Milestones
              </span>
              {goal.milestones.map((m, idx) => (
                <div key={idx} className="flex items-start gap-2 text-slate-300">
                  <CheckCircle2
                    size={14}
                    className={`shrink-0 mt-0.5 ${
                      m.completed ? "text-emerald-400" : "text-slate-600"
                    }`}
                  />
                  <span className={m.completed ? "line-through text-slate-500" : ""}>
                    {m.title}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
