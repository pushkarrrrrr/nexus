"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { MetricCard } from "../src/components/ui/MetricCard";
import { Card } from "../src/components/ui/Card";
import { StatusBadge } from "../src/components/ui/StatusBadge";
import { TaskTimeline } from "../src/components/ui/TaskTimeline";
import { ActivityFeed } from "../src/components/ui/ActivityFeed";
import { mockDAGs } from "../src/mockData/mockTasks";
import { mockApprovals } from "../src/mockData/mockApprovals";
import {
  Cpu,
  Network,
  BrainCircuit,
  ShieldCheck,
  Play,
  ArrowRight,
  Terminal,
} from "lucide-react";

export default function DashboardHome() {
  const [activePrompt, setActivePrompt] = useState("");
  const activeDAG = mockDAGs[0]; // Active task awaiting approval
  const pendingApprovalsCount = mockApprovals.length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner / Welcome Operating Context */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl md:text-2xl font-bold font-mono tracking-tight text-white">
              NEXUS KERNEL CONSOLE
            </h1>
            <StatusBadge status="online" label="ACTIVE RUNTIME" />
          </div>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Host: macOS Darwin 24.0.0 (ARM64) • Dual Surface Connected: Dashboard + Ambient HUD
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/approvals"
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 text-xs font-mono font-semibold transition-colors"
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            {pendingApprovalsCount} Action Approvals Pending
          </Link>
        </div>
      </div>

      {/* Telemetry Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Task Success Rate"
          value="93.4%"
          subvalue="Ablation: +17.3% vs RAG"
          trend="up"
          change="+17.3%"
          icon={<Network size={16} />}
        />
        <MetricCard
          label="Active DAG Steps"
          value="4 Steps"
          subvalue="1 completed, 1 awaiting approval"
          icon={<Cpu size={16} />}
        />
        <MetricCard
          label="Persistent Memory"
          value="5 Records"
          subvalue="Working, Episodic, Semantic"
          icon={<BrainCircuit size={16} />}
        />
        <MetricCard
          label="Policy Violations"
          value="0"
          subvalue="Zero tolerance safety verified"
          trend="up"
          change="100% Gated"
          icon={<ShieldCheck size={16} />}
        />
      </div>

      {/* Quick Action Input Capsule */}
      <div className="glass-panel p-4 rounded-xl border border-white/15 bg-slate-900/60 shadow-lg">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!activePrompt.trim()) return;
            alert(`Task dispatched to Orchestrator: "${activePrompt}"`);
            setActivePrompt("");
          }}
          className="flex items-center gap-3"
        >
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Terminal size={18} />
          </div>
          <input
            type="text"
            placeholder="Command NEXUS... (e.g., 'Run pytest on auth module', 'Index local docs folder', 'Refactor database models')"
            value={activePrompt}
            onChange={(e) => setActivePrompt(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-xs md:text-sm font-mono text-white placeholder-slate-500"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs flex items-center gap-1.5 transition-colors shadow-md shadow-cyan-500/20"
          >
            <Play size={14} fill="currentColor" />
            Dispatch Plan
          </button>
        </form>
      </div>

      {/* Two Column Layout: Active DAG + Live Event Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Active Plan & DAG Visualizer */}
        <div className="lg:col-span-2 space-y-6">
          <Card
            title={
              <div className="flex items-center gap-2">
                <span>Active Task DAG</span>
                <span className="text-xs font-mono text-slate-400">
                  [{activeDAG.dag_id}]
                </span>
              </div>
            }
            subtitle={activeDAG.goal}
            badge={<StatusBadge status={activeDAG.status} />}
            action={
              <Link
                href="/tasks"
                className="text-xs font-mono text-cyan-400 hover:underline flex items-center gap-1"
              >
                Inspect Graph <ArrowRight size={12} />
              </Link>
            }
          >
            {/* Step Sequence Timeline */}
            <div className="mt-4">
              <TaskTimeline nodes={activeDAG.nodes} activeNodeId="step_2" />
            </div>

            {/* In-Line Pending Approval Action Callout */}
            <div className="mt-5 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-amber-400 text-lg">⚠️</span>
                <div>
                  <span className="text-xs font-mono font-bold text-amber-300 block">
                    Execution Paused: Approval Required for Step 2
                  </span>
                  <span className="text-[11px] text-slate-300 font-mono">
                    CodingAgent wants to modify services/api/nexus_api/middleware.py
                  </span>
                </div>
              </div>
              <Link
                href="/approvals"
                className="px-3.5 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-mono font-bold text-xs transition-colors shrink-0"
              >
                Review Diff
              </Link>
            </div>
          </Card>
        </div>

        {/* Right 1 Col: Live Activity Feed */}
        <div className="space-y-6">
          <Card
            title="Live Activity Stream"
            subtitle="Core event bus broadcast"
            action={
              <span className="text-[10px] font-mono text-slate-500 uppercase">
                /ws/nexus
              </span>
            }
          >
            <ActivityFeed
              events={[
                {
                  id: "evt_1",
                  timestamp: "18:31:00",
                  type: "approval",
                  title: "Approval Requested: filesystem.modify",
                  description: "CodingAgent -> middleware.py (Risk: MEDIUM)",
                  badge: <StatusBadge risk="MEDIUM" />,
                },
                {
                  id: "evt_2",
                  timestamp: "18:30:15",
                  type: "dag",
                  title: "DAG Plan Synthesized (4 nodes)",
                  description: "PlanningAgent -> dag_901a1bc",
                  badge: <StatusBadge status="planning" />,
                },
                {
                  id: "evt_3",
                  timestamp: "18:30:12",
                  type: "tool",
                  title: "Tool Finished: filesystem.read",
                  description: "45 lines read from middleware.py (1.45ms)",
                  badge: <StatusBadge status="completed" />,
                },
                {
                  id: "evt_4",
                  timestamp: "17:45:30",
                  type: "audit",
                  title: "Audit Snapshot Recorded",
                  description: "Snapshot snap_99a81c002 captured before migration",
                  badge: <StatusBadge status="ready" />,
                },
                {
                  id: "evt_5",
                  timestamp: "17:40:00",
                  type: "system",
                  title: "Alembic Migrations Applied",
                  description: "001_initial_schema (7 tables verified)",
                  badge: <StatusBadge status="completed" />,
                },
              ]}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
