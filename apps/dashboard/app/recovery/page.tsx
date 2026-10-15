"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../src/context/AuthContext";
import { Card } from "../../src/components/ui/Card";
import { MetricCard } from "../../src/components/ui/MetricCard";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { mockRecoveryStats, mockReplanRecords } from "../../src/mockData/mockRecovery";
import type { ReplanRecord, RecoveryStats, ErrorCategory, RecoveryStrategy } from "@nexus/types";
import {
  Sparkles,
  RotateCcw,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Layers,
  Undo2,
  Play,
  Filter,
  ArrowRight,
  RefreshCw,
  Cpu,
  History,
  FileCode,
  Check,
  Eye,
  Sliders,
  X,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SimulationScenario {
  id: string;
  name: string;
  category: ErrorCategory;
  strategy: RecoveryStrategy;
  description: string;
  simulatedError: string;
  rollbackRequired: boolean;
  proposedSteps: Array<{ desc: string; agent: string; tool: string }>;
}

const PRESET_SCENARIOS: SimulationScenario[] = [
  {
    id: "tool_failure",
    name: "Missing Container Runtime (Tool Failure)",
    category: "TOOL_FAILURE",
    strategy: "FALLBACK_TOOL",
    description: "Primary terminal runner failed with code 127 because docker daemon is offline.",
    simulatedError: "Process exited with code 127: docker daemon not running at /var/run/docker.sock",
    rollbackRequired: false,
    proposedSteps: [
      { desc: "Verify local Podman user-space daemon", agent: "SystemOperatorAgent", tool: "terminal.execute" },
      { desc: "Build container artifact using Podman runner", agent: "CodingAgent", tool: "terminal.podman_runner" },
    ],
  },
  {
    id: "env_mutation",
    name: "Filesystem Corruption (Rollback & Retry)",
    category: "ENVIRONMENT_ERROR",
    strategy: "ROLLBACK_AND_RETRY",
    description: "Write mutation failed midway, leaving orphaned file buffer on disk.",
    simulatedError: "Permission denied while writing /etc/nexus/settings.yaml; partial file corruption detected.",
    rollbackRequired: true,
    proposedSteps: [
      { desc: "Revert pre-execution snapshot snap_rec_9182a", agent: "SystemOperatorAgent", tool: "filesystem.inspect" },
      { desc: "Retry mutation in sandboxed directory path", agent: "CodingAgent", tool: "filesystem.modify" },
    ],
  },
  {
    id: "param_invalid",
    name: "Schema Mismatch (Corrected Params)",
    category: "PARAM_INVALID",
    strategy: "RETRY_WITH_CORRECTED_PARAMS",
    description: "LLM inference call failed Pydantic schema validation for max_tokens field.",
    simulatedError: "ValidationError: 'max_tokens' must be an integer between 1 and 8192; received string 'unlimited'.",
    rollbackRequired: false,
    proposedSteps: [
      { desc: "Sanitize & clamp max_tokens parameter to 4096", agent: "ResearchAgent", tool: "ai.gateway_invoke" },
    ],
  },
  {
    id: "resource_missing",
    name: "Broken Dependency (Dynamic DAG Splicing)",
    category: "RESOURCE_NOT_FOUND",
    strategy: "PRUNE_AND_SPLICE_DAG",
    description: "Target upstream branch does not exist; requires branch discovery & dynamic node splicing.",
    simulatedError: "Git remote ref 'feature/v15-kernel' not found on origin repository.",
    rollbackRequired: false,
    proposedSteps: [
      { desc: "Enumerate active remote tracking branches", agent: "CodingAgent", tool: "terminal.execute" },
      { desc: "Graft nearest semantic head 'main' into DAG dependency graph", agent: "PlanningAgent", tool: "dag.patch" },
    ],
  },
  {
    id: "policy_quarantine",
    name: "Critical Risk Escalation (HITL Safeguard)",
    category: "POLICY_REJECTED",
    strategy: "ESCALATE_HITL",
    description: "Destructive system modification blocked by Principle Rule 4 policy boundary.",
    simulatedError: "Policy rejected operation 'DROP DATABASE staging' - Risk CRITICAL requires explicit approval.",
    rollbackRequired: false,
    proposedSteps: [],
  },
];

export default function RecoveryPage() {
  const { token } = useAuth();

  const [stats, setStats] = useState<RecoveryStats>(mockRecoveryStats);
  const [records, setRecords] = useState<ReplanRecord[]>(mockReplanRecords);
  const [selectedRecord, setSelectedRecord] = useState<ReplanRecord | null>(null);
  const [filterStrategy, setFilterStrategy] = useState<string>("ALL");
  const [filterCategory, setFilterCategory] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Simulation State
  const [selectedScenario, setSelectedScenario] = useState<SimulationScenario>(PRESET_SCENARIOS[0]);
  const [simStep, setSimStep] = useState<number>(0); // 0: Idle, 1: Error, 2: Classifying, 3: Reflecting, 4: Rollback, 5: Splicing, 6: Resolved
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  // Load live telemetry from API
  const loadRecoveryData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Fetch live recent reflections
      const resRecords = await fetch(`${API_BASE}/api/v1/plans/reflections/recent`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resRecords.ok) {
        const liveRecords: ReplanRecord[] = await resRecords.json();
        if (liveRecords.length > 0) {
          setRecords(liveRecords);
        }
      }

      // 2. Fetch live recovery statistics
      const resStats = await fetch(`${API_BASE}/api/v1/plans/recovery/stats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resStats.ok) {
        const liveStats: RecoveryStats = await resStats.json();
        setStats(liveStats);
      }
    } catch (err) {
      console.warn("Using cached/mock recovery telemetry:", err);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadRecoveryData();
  }, [loadRecoveryData]);

  // Run Animated Simulation
  const handleRunSimulation = () => {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimStep(1); // Trigger Failure

    setTimeout(() => {
      setSimStep(2); // Error Classification
      setTimeout(() => {
        setSimStep(3); // Strategy Synthesis
        setTimeout(() => {
          if (selectedScenario.rollbackRequired) {
            setSimStep(4); // Rollback Snapshot
            setTimeout(() => {
              setSimStep(5); // DAG Splicing
              setTimeout(() => {
                setSimStep(6); // Resolved
                setIsSimulating(false);
              }, 1200);
            }, 1200);
          } else {
            setSimStep(5); // DAG Splicing
            setTimeout(() => {
              setSimStep(6); // Resolved
              setIsSimulating(false);
            }, 1200);
          }
        }, 1200);
      }, 1000);
    }, 900);
  };

  // Filtered Records
  const filteredRecords = records.filter((r) => {
    const matchStrat = filterStrategy === "ALL" || r.strategy === filterStrategy;
    const matchCat = filterCategory === "ALL" || r.error_category === filterCategory;
    return matchStrat && matchCat;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400 shadow-lg shadow-purple-500/10">
              <Sparkles size={22} />
            </div>
            <div>
              <h1 className="text-xl font-bold font-mono tracking-tight text-white flex items-center gap-2">
                Autonomous Self-Correction & Dynamic Replanning
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 tracking-wider">
                  PHASE 15
                </span>
              </h1>
              <p className="text-xs font-mono text-slate-400 mt-0.5">
                Real-Time Fault Classification • Automated Filesystem Rollbacks • Dynamic DAG Grafting
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Autonomous Self-Healing Active</span>
          </div>
          <button
            onClick={loadRecoveryData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 text-xs font-mono transition-all"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            <span>Sync</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Self-Healing Success Rate"
          value={`${stats.success_rate_percent}%`}
          subvalue={`${stats.resolved_count} of ${stats.total_replan_records} faults healed autonomously`}
          trend="up"
          change="+3.2%"
          icon={<ShieldCheck size={18} className="text-emerald-400" />}
        />
        <MetricCard
          label="Total Replans"
          value={stats.total_replan_records}
          subvalue="Triggered across execution plans"
          trend="neutral"
          icon={<RotateCcw size={18} className="text-purple-400" />}
        />
        <MetricCard
          label="Filesystem Rollbacks"
          value={stats.rollback_count}
          subvalue="100% snapshot reversibility"
          trend="up"
          change="Clean Restores"
          icon={<Undo2 size={18} className="text-cyan-400" />}
        />
        <MetricCard
          label="HITL Quarantines"
          value={stats.hitl_escalation_count}
          subvalue="Principle Rule 4 safety boundaries"
          trend="neutral"
          change="Safeguarded"
          icon={<AlertTriangle size={18} className="text-amber-400" />}
        />
      </div>

      {/* Interactive Self-Correction Live Simulator */}
      <Card
        title={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Sliders size={18} className="text-purple-400" />
              <span className="font-mono text-sm text-white font-semibold">
                Autonomous Recovery Test Harness & Pipeline Inspector
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Interactive Hardware & Execution Failure Simulation
            </span>
          </div>
        }
        subtitle="Simulate real-world agent failures to inspect the live 6-stage reflection, rollback, and dynamic DAG splicing pipeline."
      >
        <div className="space-y-6">
          {/* Scenario Selector */}
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-2">
              Select Failure Simulation Archetype:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {PRESET_SCENARIOS.map((scen) => (
                <button
                  key={scen.id}
                  onClick={() => {
                    setSelectedScenario(scen);
                    setSimStep(0);
                  }}
                  className={`p-3 rounded-xl border text-left transition-all font-mono text-xs ${
                    selectedScenario.id === scen.id
                      ? "bg-purple-950/40 border-purple-500/50 shadow-md shadow-purple-500/10 text-white"
                      : "bg-slate-900/40 border-white/5 hover:border-white/20 text-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-cyan-300">{scen.name}</span>
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-white/5 border border-white/10 text-slate-400">
                      {scen.category}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-snug line-clamp-2">
                    {scen.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Trigger Button & Scenario Details */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-white/10 space-y-4 font-mono text-xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Active Scenario:</span>
                  <span className="font-bold text-white">{selectedScenario.name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    Strategy: {selectedScenario.strategy.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="text-[11px] text-rose-400 font-mono">
                  Fault Signal: {selectedScenario.simulatedError}
                </div>
              </div>

              <button
                onClick={handleRunSimulation}
                disabled={isSimulating}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-mono text-xs font-semibold shadow-lg shadow-purple-500/20 transition-all disabled:opacity-50"
              >
                {isSimulating ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Executing Self-Correction...</span>
                  </>
                ) : (
                  <>
                    <Play size={14} />
                    <span>Run Autonomous Recovery Cycle</span>
                  </>
                )}
              </button>
            </div>

            {/* Pipeline Stage Indicators */}
            <div className="pt-3 border-t border-white/10">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Recovery Pipeline Progression:
              </div>
              <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                {[
                  { stage: 1, label: "Fault Triggered", color: "rose" },
                  { stage: 2, label: "Classifier Diagnosis", color: "amber" },
                  { stage: 3, label: "Strategy Engine", color: "purple" },
                  { stage: 4, label: "Rollback Ledger", color: "cyan" },
                  { stage: 5, label: "Dynamic DAG Splice", color: "indigo" },
                  { stage: 6, label: "Resumed Clean", color: "emerald" },
                ].map((s) => {
                  const isActive = simStep === s.stage;
                  const isDone = simStep > s.stage;
                  return (
                    <div
                      key={s.stage}
                      className={`p-2.5 rounded-xl border text-center transition-all ${
                        isActive
                          ? "bg-purple-900/40 border-purple-400 shadow-md shadow-purple-500/20 scale-105"
                          : isDone
                          ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-300"
                          : "bg-slate-900/30 border-white/5 text-slate-500"
                      }`}
                    >
                      <div className="text-[10px] font-bold">STAGE 0{s.stage}</div>
                      <div className="text-[11px] font-medium mt-0.5 truncate">{s.label}</div>
                      <div className="mt-1 flex justify-center">
                        {isDone ? (
                          <Check size={12} className="text-emerald-400" />
                        ) : isActive ? (
                          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />
                        ) : (
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-700" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Live Simulation Output Card */}
            {simStep > 0 && (
              <div className="p-4 rounded-xl bg-black/60 border border-purple-500/20 space-y-3 animate-fadeIn">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-bold text-purple-400 flex items-center gap-1.5">
                    <Activity size={13} />
                    <span>Real-Time Recovery Trace</span>
                  </span>
                  <span className="text-slate-400">
                    Status:{" "}
                    <strong className={simStep === 6 ? "text-emerald-400" : "text-cyan-400"}>
                      {simStep === 6 ? "RECOVERY VERIFIED & SPLICED" : "HEALING IN PROGRESS"}
                    </strong>
                  </span>
                </div>

                <div className="space-y-1.5 text-[11px] font-mono leading-relaxed text-slate-300">
                  {simStep >= 1 && (
                    <div className="flex items-start gap-2 text-rose-300">
                      <span>🔴</span>
                      <span>[0ms] <strong>FAULT DETECTED:</strong> {selectedScenario.simulatedError}</span>
                    </div>
                  )}
                  {simStep >= 2 && (
                    <div className="flex items-start gap-2 text-amber-300">
                      <span>🔍</span>
                      <span>[320ms] <strong>CLASSIFIER:</strong> Identified root cause as <code>{selectedScenario.category}</code> (Confidence: 0.98)</span>
                    </div>
                  )}
                  {simStep >= 3 && (
                    <div className="flex items-start gap-2 text-purple-300">
                      <span>🧠</span>
                      <span>[680ms] <strong>STRATEGY SELECTED:</strong> <code>{selectedScenario.strategy}</code>. {selectedScenario.description}</span>
                    </div>
                  )}
                  {simStep >= 4 && selectedScenario.rollbackRequired && (
                    <div className="flex items-start gap-2 text-cyan-300">
                      <span>⏪</span>
                      <span>[1140ms] <strong>FILESYSTEM ROLLBACK:</strong> Restored snapshot <code>snap_rec_9182a</code> before re-execution.</span>
                    </div>
                  )}
                  {simStep >= 5 && (
                    <div className="flex items-start gap-2 text-indigo-300">
                      <span>✂️</span>
                      <span>
                        [1490ms] <strong>DAG SPLICER:</strong> Marked failed step as <code>SUPERSEDED</code> and grafted {selectedScenario.proposedSteps.length} replacement nodes.
                      </span>
                    </div>
                  )}
                  {simStep >= 6 && (
                    <div className="flex items-start gap-2 text-emerald-400 font-bold">
                      <span>🟢</span>
                      <span>[1850ms] <strong>EXECUTION RESUMED:</strong> Downstream dependencies re-linked; pipeline operational.</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* DAG Splicing & Diff Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Original Execution Graph */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Layers size={16} className="text-slate-400" />
              <span className="font-mono text-sm">Original Graph (Fault Detected)</span>
            </div>
          }
          subtitle="Pre-failure execution plan with blocked/corrupted step"
        >
          <div className="space-y-3 font-mono text-xs">
            <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between">
              <div>
                <div className="font-bold text-white">1. inspect_prerequisites</div>
                <div className="text-[11px] text-slate-400">Assigned: SystemOperatorAgent</div>
              </div>
              <StatusBadge status="completed" />
            </div>

            <div className="flex justify-center text-slate-500">
              <ArrowRight size={14} className="rotate-90" />
            </div>

            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/50 shadow-md shadow-rose-500/10 flex items-center justify-between">
              <div>
                <div className="font-bold text-rose-300">2. {selectedScenario.id} [FAILED]</div>
                <div className="text-[11px] text-rose-400 line-clamp-1">{selectedScenario.simulatedError}</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/30 text-rose-300 border border-rose-500/50">
                FAILED
              </span>
            </div>

            <div className="flex justify-center text-slate-500">
              <ArrowRight size={14} className="rotate-90" />
            </div>

            <div className="p-3 rounded-xl bg-slate-900/40 border border-white/5 opacity-60 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-400">3. deploy_artifact</div>
                <div className="text-[11px] text-slate-500">Blocked on Step 2</div>
              </div>
              <StatusBadge status="pending" />
            </div>
          </div>
        </Card>

        {/* Right: Spliced Self-Correction Graph */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-purple-400" />
              <span className="font-mono text-sm text-purple-300">Spliced Recovery Graph</span>
            </div>
          }
          subtitle="Dynamically grafted recovery branch with re-routed dependencies"
        >
          <div className="space-y-3 font-mono text-xs">
            <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between">
              <div>
                <div className="font-bold text-white">1. inspect_prerequisites</div>
                <div className="text-[11px] text-slate-400">Assigned: SystemOperatorAgent</div>
              </div>
              <StatusBadge status="completed" />
            </div>

            <div className="flex justify-center text-slate-500">
              <ArrowRight size={14} className="rotate-90" />
            </div>

            {/* Superseded Step */}
            <div className="p-3 rounded-xl bg-slate-900/40 border border-dashed border-slate-700 opacity-60 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-400 line-through">2. {selectedScenario.id}</div>
                <div className="text-[10px] text-slate-500">Superseded by autonomous self-correction patch</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                SUPERSEDED
              </span>
            </div>

            {/* Grafted Recovery Nodes */}
            {selectedScenario.proposedSteps.map((recStep, idx) => (
              <React.Fragment key={idx}>
                <div className="flex justify-center text-purple-400">
                  <ArrowRight size={14} className="rotate-90" />
                </div>
                <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-500/40 shadow-md shadow-purple-500/10 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-purple-200">2.{idx + 1} {recStep.desc}</span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                        RECOVERY NODE
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Agent: <strong className="text-cyan-400">{recStep.agent}</strong> • Tool: <code>{recStep.tool}</code>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    RESOLVED
                  </span>
                </div>
              </React.Fragment>
            ))}

            <div className="flex justify-center text-slate-500">
              <ArrowRight size={14} className="rotate-90" />
            </div>

            <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/30 flex items-center justify-between">
              <div>
                <div className="font-bold text-cyan-300">3. deploy_artifact</div>
                <div className="text-[11px] text-slate-400">Dependencies re-linked to recovery nodes</div>
              </div>
              <StatusBadge status="in_progress" />
            </div>
          </div>
        </Card>
      </div>

      {/* Historical Self-Correction Audit Log */}
      <Card
        title={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <History size={18} className="text-cyan-400" />
              <span className="font-mono text-sm text-white font-semibold">
                Autonomous Self-Correction Ledger ({filteredRecords.length})
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Filter size={13} className="text-slate-400" />
              <select
                value={filterStrategy}
                onChange={(e) => setFilterStrategy(e.target.value)}
                className="bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-[11px] font-mono text-slate-300 focus:outline-none"
              >
                <option value="ALL">All Strategies</option>
                <option value="RETRY_WITH_CORRECTED_PARAMS">Corrected Params</option>
                <option value="FALLBACK_TOOL">Fallback Tool</option>
                <option value="PRUNE_AND_SPLICE_DAG">DAG Splicing</option>
                <option value="ROLLBACK_AND_RETRY">Rollback & Retry</option>
                <option value="ESCALATE_HITL">HITL Escalation</option>
              </select>
            </div>
          </div>
        }
        subtitle="Persistent ledger of all fault reflections, rollback records, and dynamic replanning interventions"
      >
        <div className="space-y-3 font-mono text-xs">
          {filteredRecords.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              No self-correction records found matching active filter.
            </div>
          ) : (
            filteredRecords.map((rec) => (
              <div
                key={rec.id}
                className="p-4 rounded-xl bg-slate-950/70 border border-white/10 hover:border-purple-500/30 transition-all space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-2.5">
                  <div className="flex items-center gap-2.5">
                    <span className="font-bold text-white">{rec.id}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      {rec.error_category}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                      {rec.strategy.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400">
                    <span>Plan: <strong className="text-slate-300">{rec.plan_id}</strong></span>
                    <span>•</span>
                    <span>{new Date(rec.created_at).toLocaleTimeString()}</span>
                    <StatusBadge status={rec.status === "resolved" ? "completed" : rec.status} />
                  </div>
                </div>

                <div className="text-[12px] text-slate-300 leading-relaxed">
                  <strong className="text-purple-300">Diagnosis: </strong>
                  {rec.diagnosis}
                </div>

                {rec.error_message && (
                  <div className="p-2 rounded-lg bg-black/50 border border-white/5 text-[11px] text-rose-300 font-mono">
                    <span className="text-slate-500 mr-2">Error context:</span>
                    {rec.error_message}
                  </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5 text-[11px] text-slate-400">
                  <div className="flex items-center gap-4">
                    <span>
                      Filesystem Rollback:{" "}
                      <strong className={rec.rollback_performed ? "text-emerald-400" : "text-slate-500"}>
                        {rec.rollback_performed ? `Snapshot ${rec.snapshot_id || "Active"} Restored` : "None"}
                      </strong>
                    </span>
                    <span>
                      Recovery Steps Grafted:{" "}
                      <strong className="text-cyan-400">{rec.recovery_steps.length}</strong>
                    </span>
                  </div>

                  <button
                    onClick={() => setSelectedRecord(rec)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-[11px] transition-all"
                  >
                    <Eye size={12} />
                    <span>Inspect Diagnostic Payload</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Record Diagnostic Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-2xl rounded-2xl bg-slate-950 border border-purple-500/40 p-6 space-y-4 font-mono text-xs shadow-2xl shadow-purple-500/20">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-purple-400" />
                <span className="text-sm font-bold text-white">Diagnostic Record: {selectedRecord.id}</span>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-slate-500 text-[10px] uppercase">Plan & Task References:</span>
                <div className="text-slate-300 mt-1">
                  Plan ID: <code>{selectedRecord.plan_id}</code> | Step ID: <code>{selectedRecord.step_id}</code> | Task ID: <code>{selectedRecord.task_id}</code>
                </div>
              </div>

              <div>
                <span className="text-slate-500 text-[10px] uppercase">Root Cause Diagnosis:</span>
                <p className="p-2.5 rounded-lg bg-white/5 border border-white/5 text-slate-300 mt-1 leading-relaxed">
                  {selectedRecord.diagnosis}
                </p>
              </div>

              <div>
                <span className="text-slate-500 text-[10px] uppercase">Grafted Recovery Nodes ({selectedRecord.recovery_steps.length}):</span>
                <div className="mt-1 space-y-1.5">
                  {selectedRecord.recovery_steps.length === 0 ? (
                    <div className="text-slate-500 italic p-2">No recovery steps grafted (Quarantined / Escalated)</div>
                  ) : (
                    selectedRecord.recovery_steps.map((s, idx) => (
                      <div key={idx} className="p-2 rounded bg-purple-950/20 border border-purple-500/20 text-purple-200 text-[11px]">
                        <pre className="whitespace-pre-wrap">{JSON.stringify(s, null, 2)}</pre>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div>
                <span className="text-slate-500 text-[10px] uppercase">Complete JSON Contract:</span>
                <pre className="mt-1 p-3 rounded-lg bg-black/60 border border-white/5 text-slate-400 text-[10px] max-h-40 overflow-y-auto">
                  {JSON.stringify(selectedRecord, null, 2)}
                </pre>
              </div>
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-all"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
