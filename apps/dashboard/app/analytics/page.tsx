"use client";

import React from "react";
import { mockAblations } from "../../src/mockData/mockAnalytics";
import { MetricCard } from "../../src/components/ui/MetricCard";
import { Card } from "../../src/components/ui/Card";
import { LineChart, ShieldCheck, CheckCircle2, DollarSign, Timer } from "lucide-react";

export default function AnalyticsPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Capstone Research Evaluation</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Formal ablation benchmarks evaluating Task Success, Planning Accuracy, Latency, and Cost
          </p>
        </div>
      </div>

      {/* Top Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="NEXUS Success Rate"
          value="93.4%"
          subvalue="vs. 34.2% Baseline"
          trend="up"
          change="+59.2%"
          icon={<CheckCircle2 size={16} />}
        />
        <MetricCard
          label="Planning Accuracy"
          value="96.1%"
          subvalue="Topological DAG synthesis"
          trend="up"
          change="+55.1%"
          icon={<LineChart size={16} />}
        />
        <MetricCard
          label="Safety Violations"
          value="0"
          subvalue="Enforced by Policy Engine"
          trend="up"
          change="0 Violations"
          icon={<ShieldCheck size={16} />}
        />
        <MetricCard
          label="Avg Latency / Task"
          value="8.2s"
          subvalue="Multi-step execution loop"
          icon={<Timer size={16} />}
        />
      </div>

      {/* Formal Ablation Benchmark Matrix */}
      <Card
        title="Comparative Architecture Ablation Matrix"
        subtitle="Evaluating progressive system layers on standardized benchmark tasks"
      >
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase text-[11px]">
                <th className="py-3 px-4">Architecture Configuration</th>
                <th className="py-3 px-4">Success Rate</th>
                <th className="py-3 px-4">Planning Accuracy</th>
                <th className="py-3 px-4">Avg Latency</th>
                <th className="py-3 px-4">Policy Violations</th>
                <th className="py-3 px-4">Cost / Task</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {mockAblations.map((row, idx) => {
                const isNexus = idx === mockAblations.length - 1;
                return (
                  <tr
                    key={row.configuration}
                    className={`transition-colors ${
                      isNexus
                        ? "bg-cyan-500/10 text-cyan-200 font-semibold"
                        : "hover:bg-white/5 text-slate-300"
                    }`}
                  >
                    <td className="py-3 px-4">
                      {row.configuration}
                      {isNexus && (
                        <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                          OUR PROPOSAL
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-emerald-400">
                      {row.task_success_rate}%
                    </td>
                    <td className="py-3 px-4 text-sky-400">
                      {row.planning_accuracy}%
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {row.avg_latency_sec}s
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={
                          row.safety_violations === 0
                            ? "text-emerald-400 font-bold"
                            : "text-rose-400"
                        }
                      >
                        {row.safety_violations}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      ${row.cost_per_task.toFixed(3)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
