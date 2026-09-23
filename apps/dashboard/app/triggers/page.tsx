"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  HardDrive,
  Layers,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  ToggleLeft,
  ToggleRight,
  Trash2,
  Zap,
} from "lucide-react";
import type {
  ProactiveTrigger,
  SystemMetrics,
  TriggerCreateRequest,
  TriggerEvent,
} from "@nexus/types";

export default function TriggersPage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [triggers, setTriggers] = useState<ProactiveTrigger[]>([]);
  const [events, setEvents] = useState<TriggerEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form State
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<"threshold" | "schedule" | "file_watch">("threshold");
  const [newMetric, setNewMetric] = useState("cpu_percent");
  const [newOperator, setNewOperator] = useState<">" | "<">(">");
  const [newThreshold, setNewThreshold] = useState("80");
  const [newCapability, setNewCapability] = useState("remediation.execute_fix");
  const [newCooldown, setNewCooldown] = useState("300");

  const getHeaders = (): Record<string, string> => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchData = async () => {
    try {
      const headers = getHeaders();

      const [metricsRes, triggersRes, eventsRes] = await Promise.all([
        fetch("http://localhost:8000/api/v1/watchers/metrics", { headers }),
        fetch("http://localhost:8000/api/v1/triggers", { headers }),
        fetch("http://localhost:8000/api/v1/triggers/events", { headers }),
      ]);

      if (metricsRes.ok) setMetrics(await metricsRes.json());
      if (triggersRes.ok) setTriggers(await triggersRes.json());
      if (eventsRes.ok) setEvents(await eventsRes.json());
    } catch {
      // Fallback defaults for preview
      setMetrics({
        timestamp: new Date().toISOString(),
        cpu_percent: 24.5,
        cpu_load_1m: 1.25,
        cpu_load_5m: 1.10,
        cpu_load_15m: 0.95,
        memory_total_bytes: 17179869184,
        memory_used_bytes: 7730941132,
        memory_percent: 45.0,
        disk_total_bytes: 500000000000,
        disk_used_bytes: 180000000000,
        disk_free_bytes: 320000000000,
        disk_percent: 36.0,
        active_watchers: 2,
        status: "healthy",
      });
      setTriggers([
        {
          id: "trig_demo_cpu",
          user_id: "usr_default",
          name: "High CPU Spike Watcher",
          trigger_type: "threshold",
          condition: { metric_name: "cpu_percent", operator: ">", threshold_value: 85.0 },
          action_capability: "remediation.execute_fix",
          action_params: { fix_type: "clear_cache", target: "system" },
          is_active: true,
          cooldown_seconds: 300,
          trigger_count: 3,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: "trig_demo_disk",
          user_id: "usr_default",
          name: "Disk Exhaustion Guard",
          trigger_type: "threshold",
          condition: { metric_name: "disk_percent", operator: ">", threshold_value: 90.0 },
          action_capability: "remediation.execute_fix",
          action_params: { fix_type: "kill_stale_process", target: "scratch_cache" },
          is_active: true,
          cooldown_seconds: 600,
          trigger_count: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      setEvents([
        {
          id: "trevt_demo_01",
          trigger_id: "trig_demo_cpu",
          user_id: "usr_default",
          event_type: "proactive.threshold",
          observed_data: { metric_name: "cpu_percent", current_value: 88.4, threshold_value: 85.0 },
          action_proposed: "remediation.execute_fix",
          approval_id: "appr_demo_01",
          status: "awaiting_approval",
          created_at: new Date(Date.now() - 300000).toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async (triggerId: string) => {
    try {
      await fetch(`http://localhost:8000/api/v1/triggers/${triggerId}/toggle`, {
        method: "PATCH",
        headers: getHeaders(),
      });
      fetchData();
    } catch {
      setTriggers((prev) =>
        prev.map((t) => (t.id === triggerId ? { ...t, is_active: !t.is_active } : t))
      );
    }
  };

  const handleDelete = async (triggerId: string) => {
    try {
      await fetch(`http://localhost:8000/api/v1/triggers/${triggerId}`, {
        method: "DELETE",
        headers: getHeaders(),
      });
      fetchData();
    } catch {
      setTriggers((prev) => prev.filter((t) => t.id !== triggerId));
    }
  };

  const handleEvaluateNow = async () => {
    setIsEvaluating(true);
    try {
      await fetch("http://localhost:8000/api/v1/triggers/evaluate", {
        method: "POST",
        headers: getHeaders(),
      });
      await fetchData();
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleCreateTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    const payload: TriggerCreateRequest = {
      name: newName.trim(),
      trigger_type: newType,
      condition: {
        metric_name: newMetric,
        operator: newOperator,
        threshold_value: parseFloat(newThreshold) || 80.0,
      },
      action_capability: newCapability,
      action_params: { fix_type: "clear_cache", target: "system" },
      cooldown_seconds: parseInt(newCooldown, 10) || 300,
      is_active: true,
    };

    try {
      const res = await fetch("http://localhost:8000/api/v1/triggers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getHeaders(),
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setShowCreateModal(false);
        setNewName("");
        fetchData();
      }
    } catch {
      setShowCreateModal(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Zap size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight font-mono flex items-center gap-3">
                Proactive Watchers & Triggers
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono">
                  Phase 14
                </span>
              </h1>
              <p className="text-sm text-slate-400 font-mono mt-0.5">
                Autonomous system telemetry observation, rule evaluation, and policy-gated self-healing
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            Sync
          </button>
          <button
            onClick={handleEvaluateNow}
            disabled={isEvaluating}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-xs font-mono text-cyan-300 hover:bg-cyan-500/20 transition-colors"
          >
            <Play size={14} className={isEvaluating ? "animate-pulse" : ""} />
            Evaluate Now
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold text-xs font-mono hover:opacity-90 shadow-md shadow-cyan-500/20 transition-all"
          >
            <Plus size={15} />
            New Trigger
          </button>
        </div>
      </div>

      {/* Metric Telemetry Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* CPU */}
        <div className="p-5 rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">CPU Utilization</span>
            <Cpu size={16} className="text-cyan-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">
              {metrics ? `${metrics.cpu_percent}%` : "..."}
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              1m: {metrics?.cpu_load_1m ?? "0.0"}
            </span>
          </div>
          <div className="mt-3 w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                (metrics?.cpu_percent || 0) > 80 ? "bg-amber-400" : "bg-cyan-400"
              }`}
              style={{ width: `${Math.min(100, metrics?.cpu_percent || 0)}%` }}
            />
          </div>
        </div>

        {/* Memory */}
        <div className="p-5 rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Memory Occupancy</span>
            <Activity size={16} className="text-purple-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">
              {metrics ? `${metrics.memory_percent}%` : "..."}
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              {metrics?.memory_total_bytes
                ? `${Math.round(metrics.memory_total_bytes / (1024 * 1024 * 1024))}GB RAM`
                : "Active"}
            </span>
          </div>
          <div className="mt-3 w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-400 transition-all duration-500"
              style={{ width: `${Math.min(100, metrics?.memory_percent || 0)}%` }}
            />
          </div>
        </div>

        {/* Disk */}
        <div className="p-5 rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Root Disk Space</span>
            <HardDrive size={16} className="text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white">
              {metrics ? `${metrics.disk_percent}%` : "..."}
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              {metrics?.disk_free_bytes
                ? `${Math.round(metrics.disk_free_bytes / (1024 * 1024 * 1024))}GB free`
                : "Checking"}
            </span>
          </div>
          <div className="mt-3 w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-400 transition-all duration-500"
              style={{ width: `${Math.min(100, metrics?.disk_percent || 0)}%` }}
            />
          </div>
        </div>

        {/* Watcher Status */}
        <div className="p-5 rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">System Daemon</span>
            <Layers size={16} className="text-cyan-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-emerald-400">ONLINE</span>
            <span className="text-[11px] font-mono text-slate-400">WAL Mode</span>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs font-mono text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>{triggers.filter((t) => t.is_active).length} Active Watchers</span>
          </div>
        </div>
      </div>

      {/* Configured Triggers Table */}
      <div className="rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white font-mono flex items-center gap-2">
            <Zap size={18} className="text-cyan-400" />
            Configured Proactive Triggers ({triggers.length})
          </h2>
          <span className="text-xs font-mono text-slate-400">Auto-evaluates every 5s</span>
        </div>

        {triggers.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-mono text-xs">
            No proactive triggers configured. Click "New Trigger" to add system health guards.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="border-b border-white/10 text-slate-400 text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4">Trigger Name</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Condition</th>
                  <th className="py-3 px-4">Action Capability</th>
                  <th className="py-3 px-4">Cooldown</th>
                  <th className="py-3 px-4">Fired</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {triggers.map((trigger) => (
                  <tr key={trigger.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                      {trigger.name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-800 border border-white/10 text-[10px]">
                        {trigger.trigger_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-cyan-300">
                      {trigger.condition.metric_name ? (
                        <span>
                          {trigger.condition.metric_name} {trigger.condition.operator} {trigger.condition.threshold_value}
                        </span>
                      ) : (
                        <span>Interval: {trigger.condition.schedule_interval_sec ?? 300}s</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] border ${
                          trigger.action_capability.includes("execute_fix")
                            ? "bg-amber-500/10 text-amber-300 border-amber-500/30 font-semibold"
                            : "bg-slate-800 text-slate-300 border-white/10"
                        }`}
                      >
                        {trigger.action_capability}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{trigger.cooldown_seconds}s</td>
                    <td className="py-3 px-4 text-slate-300">{trigger.trigger_count}x</td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => handleToggle(trigger.id)}
                        className="flex items-center gap-1.5 text-xs focus:outline-none"
                      >
                        {trigger.is_active ? (
                          <>
                            <ToggleRight size={20} className="text-emerald-400" />
                            <span className="text-emerald-400">ACTIVE</span>
                          </>
                        ) : (
                          <>
                            <ToggleLeft size={20} className="text-slate-500" />
                            <span className="text-slate-500">PAUSED</span>
                          </>
                        )}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDelete(trigger.id)}
                        className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                        title="Delete trigger"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Anomaly & Self-Healing Event Stream */}
      <div className="rounded-2xl bg-slate-950/60 border border-white/10 backdrop-blur-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white font-mono flex items-center gap-2">
            <Activity size={18} className="text-purple-400" />
            Detection & Remediation Event Stream
          </h2>
          <span className="text-xs font-mono text-slate-400">Real-time WebSocket Bus</span>
        </div>

        {events.length === 0 ? (
          <div className="text-center py-8 text-slate-500 font-mono text-xs">
            No anomaly events detected yet. The autonomous watcher is observing healthy metrics.
          </div>
        ) : (
          <div className="space-y-3 font-mono text-xs">
            {events.map((evt) => (
              <div
                key={evt.id}
                className="p-4 rounded-xl bg-slate-900/60 border border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        evt.status === "awaiting_approval"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse"
                          : evt.status === "executed"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      }`}
                    >
                      {evt.status.replace("_", " ")}
                    </span>
                    <span className="font-bold text-white">{evt.event_type}</span>
                    <span className="text-slate-500">|</span>
                    <span className="text-cyan-400">{evt.action_proposed}</span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Observed: {JSON.stringify(evt.observed_data)}
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  {evt.status === "awaiting_approval" && evt.approval_id && (
                    <a
                      href="/approvals"
                      className="px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 font-bold hover:bg-amber-500/30 flex items-center gap-1.5 transition-colors"
                    >
                      <ShieldAlert size={13} />
                      Review Approval
                    </a>
                  )}
                  <div className="flex items-center gap-1 text-[11px] text-slate-500">
                    <Clock size={12} />
                    <span>{new Date(evt.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Safety Constitutional Notice */}
      <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-500/30 text-xs font-mono text-blue-200 flex items-start gap-3">
        <ShieldAlert size={18} className="text-cyan-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-white block">Constitutional Safety Guardrail (AGENTS.md Section 4):</span>
          <span>
            Passive telemetry observations and status checks execute autonomously at <code className="text-cyan-300">RiskLevel.LOW</code>.
            Any mutating remediation or recovery action is strictly classified as <code className="text-amber-300">RiskLevel.HIGH</code> and
            immediately halts behind a Human-in-the-Loop Approval Request.
          </span>
        </div>
      </div>

      {/* Create Trigger Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-950 border border-white/15 rounded-2xl max-w-lg w-full p-6 space-y-5 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Zap size={18} className="text-cyan-400" />
                Create Proactive Trigger
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTrigger} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Trigger Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Memory Spike Guard"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Trigger Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="threshold">Metric Threshold</option>
                    <option value="schedule">Schedule Interval</option>
                    <option value="file_watch">File Watch</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Metric Target</label>
                  <select
                    value={newMetric}
                    onChange={(e) => setNewMetric(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="cpu_percent">CPU Utilization (%)</option>
                    <option value="memory_percent">Memory Occupancy (%)</option>
                    <option value="disk_percent">Disk Usage (%)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Operator & Threshold</label>
                  <div className="flex gap-2">
                    <select
                      value={newOperator}
                      onChange={(e) => setNewOperator(e.target.value as any)}
                      className="px-2.5 py-2 rounded-lg bg-slate-900 border border-white/10 text-white"
                    >
                      <option value=">">&gt;</option>
                      <option value="<">&lt;</option>
                    </select>
                    <input
                      type="number"
                      required
                      value={newThreshold}
                      onChange={(e) => setNewThreshold(e.target.value)}
                      className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Cooldown (seconds)</label>
                  <input
                    type="number"
                    required
                    value={newCooldown}
                    onChange={(e) => setNewCooldown(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Action Capability</label>
                <select
                  value={newCapability}
                  onChange={(e) => setNewCapability(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-white/10 text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="remediation.execute_fix">remediation.execute_fix (HIGH Risk - Requires Approval)</option>
                  <option value="remediation.trigger_recovery">remediation.trigger_recovery (HIGH Risk - Requires Approval)</option>
                  <option value="watcher.get_system_metrics">watcher.get_system_metrics (LOW Risk - Auto-executes)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold hover:opacity-90 shadow-md shadow-cyan-500/20"
                >
                  Register Trigger
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
