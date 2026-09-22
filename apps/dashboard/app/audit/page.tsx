"use client";

import React, { useState, useEffect, useCallback } from "react";
import { mockAuditLogs } from "../../src/mockData/mockAuditLogs";
import { DataTable, type Column } from "../../src/components/ui/DataTable";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { DiffViewer } from "../../src/components/ui/DiffViewer";
import { useAuth } from "../../src/context/AuthContext";
import type { AuditEvent, RiskLevel, ActionSnapshot } from "@nexus/types";
import {
  RefreshCw,
  ShieldCheck,
  Filter,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  X,
  History,
  FileCode,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AuditPage() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<"AUDIT_EVENTS" | "SNAPSHOTS">("AUDIT_EVENTS");

  // Audit Logs State
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [riskFilter, setRiskFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Snapshots State
  const [snapshots, setSnapshots] = useState<ActionSnapshot[]>([]);
  const [snapshotsLoading, setSnapshotsLoading] = useState<boolean>(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<ActionSnapshot | null>(null);
  const [isReverting, setIsReverting] = useState<boolean>(false);
  const [forceRevert, setForceRevert] = useState<boolean>(false);
  const [revertResult, setRevertResult] = useState<{ success: boolean; message: string } | null>(null);

  const fetchAuditLogs = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (riskFilter !== "ALL") params.append("risk_level", riskFilter);
      if (statusFilter !== "ALL") params.append("status", statusFilter);

      const url = `${API_BASE}/api/v1/policy/audit?${params.toString()}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        const data = await res.json();
        if (data.items && Array.isArray(data.items)) {
          const mapped: AuditEvent[] = data.items.map((item: {
            id: string;
            timestamp?: string;
            created_at: string;
            session_id?: string;
            step_id?: string;
            agent_name: string;
            tool_name: string;
            action_type: string;
            risk_level: RiskLevel;
            details?: Record<string, unknown>;
            status: string;
            policy_verdict: string;
            event_type?: string;
            capability_name?: string;
            ip_address?: string;
          }) => ({
            event_id: item.id,
            timestamp: item.timestamp || item.created_at,
            session_id: item.session_id || "system",
            step_id: item.step_id,
            agent_name: item.agent_name,
            tool_name: item.capability_name || item.tool_name,
            action_type: item.action_type as AuditEvent["action_type"],
            risk_level: item.risk_level,
            inputs: item.details || {},
            policy_decision: (item.status === "BLOCKED" || item.policy_verdict === "BLOCKED")
              ? "blocked_by_policy"
              : (item.policy_verdict === "APPROVED" || item.policy_verdict === "ALLOWED")
              ? "approved_by_user"
              : "auto_approved",
            execution_duration_ms: 1.0,
            undo_registered: false,
            event_type: item.event_type || "POLICY_CHECK",
            status: item.status,
            capability_name: item.capability_name,
          }));
          setLogs(mapped);
          setIsLoading(false);
          return;
        }
      }
      throw new Error("Using fallback mock audit records");
    } catch {
      let filtered = [...mockAuditLogs];
      if (riskFilter !== "ALL") {
        filtered = filtered.filter((l) => l.risk_level === riskFilter);
      }
      setLogs(filtered);
    } finally {
      setIsLoading(false);
    }
  }, [token, riskFilter, statusFilter]);

  const fetchSnapshots = useCallback(async () => {
    setSnapshotsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reversal/snapshots`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        if (data.items && Array.isArray(data.items)) {
          setSnapshots(data.items);
        }
      }
    } catch {
      // Fallback empty snapshots
    } finally {
      setSnapshotsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (activeTab === "AUDIT_EVENTS") {
      fetchAuditLogs();
    } else {
      fetchSnapshots();
    }
  }, [activeTab, fetchAuditLogs, fetchSnapshots]);

  const handleRevert = async () => {
    if (!selectedSnapshot) return;
    setIsReverting(true);
    setRevertResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reversal/snapshots/${selectedSnapshot.id}/revert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ force: forceRevert }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Revert failed (status ${res.status})`);
      }

      setRevertResult({
        success: true,
        message: data.message || `Successfully rolled back action on ${data.target_path || "resource"}.`,
      });
      fetchSnapshots();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute revert.";
      setRevertResult({ success: false, message: msg });
    } finally {
      setIsReverting(false);
    }
  };

  const auditColumns: Column<AuditEvent>[] = [
    {
      key: "event_id",
      header: "Event ID",
      render: (item) => (
        <span className="font-mono text-cyan-400 font-medium">
          {item.event_id}
        </span>
      ),
    },
    {
      key: "timestamp",
      header: "Timestamp",
      render: (item) => (
        <span className="font-mono text-slate-400 text-[11px]">
          {new Date(item.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </span>
      ),
    },
    {
      key: "agent_name",
      header: "Actor",
      render: (item) => (
        <span className="font-mono text-slate-300 text-xs">{item.agent_name}</span>
      ),
    },
    {
      key: "tool_name",
      header: "Capability & Action",
      render: (item) => (
        <div className="font-mono">
          <span className="text-white block font-medium">{item.tool_name}</span>
          <span className="text-[10px] text-slate-500 uppercase">
            {item.action_type}
          </span>
        </div>
      ),
    },
    {
      key: "risk_level",
      header: "Risk",
      render: (item) => <StatusBadge risk={item.risk_level} />,
    },
    {
      key: "policy_decision",
      header: "Verdict / Status",
      render: (item) => {
        const isBlocked =
          item.policy_decision === "blocked_by_policy" ||
          item.status === "BLOCKED" ||
          item.status === "DENIED";
        const isApproved =
          item.policy_decision === "approved_by_user" ||
          item.status === "SUCCESS";

        return (
          <span
            className={`font-mono text-[11px] font-semibold uppercase px-2 py-0.5 rounded border ${
              isBlocked
                ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                : isApproved
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
            }`}
          >
            {item.status || item.policy_decision.replace(/_/g, " ")}
          </span>
        );
      },
    },
    {
      key: "actions",
      header: "Audit Type",
      render: (item) => (
        <span className="font-mono text-[11px] text-slate-400">
          {item.event_type || "POLICY_CHECK"}
        </span>
      ),
    },
  ];

  const snapshotColumns: Column<ActionSnapshot>[] = [
    {
      key: "id",
      header: "Snapshot ID",
      render: (item) => (
        <span className="font-mono text-cyan-400 font-medium text-xs">
          {item.id}
        </span>
      ),
    },
    {
      key: "target_path",
      header: "Target Resource",
      render: (item) => (
        <span className="font-mono text-slate-200 text-xs truncate max-w-xs block" title={item.target_path || ""}>
          {item.target_path || "N/A"}
        </span>
      ),
    },
    {
      key: "action_type",
      header: "Action Type",
      render: (item) => (
        <div className="flex items-center gap-1.5 font-mono text-xs">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {item.action_type}
          </span>
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] border ${
              item.is_reversible
                ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                : "bg-amber-500/15 text-amber-300 border-amber-500/30"
            }`}
          >
            {item.is_reversible ? "Reversible" : "Permanent"}
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (item) => {
        let color = "bg-cyan-500/15 text-cyan-300 border-cyan-500/30";
        if (item.status === "REVERTED") color = "bg-purple-500/15 text-purple-300 border-purple-500/30";
        if (item.status === "FAILED") color = "bg-rose-500/15 text-rose-300 border-rose-500/30";
        return (
          <span className={`font-mono text-[11px] font-semibold px-2 py-0.5 rounded border ${color}`}>
            {item.status}
          </span>
        );
      },
    },
    {
      key: "created_at",
      header: "Created",
      render: (item) => (
        <span className="font-mono text-slate-400 text-[11px]">
          {new Date(item.created_at).toLocaleTimeString()}
        </span>
      ),
    },
    {
      key: "diff_patch",
      header: "Rollback Actions",
      render: (item) => (
        <button
          onClick={() => {
            setSelectedSnapshot(item);
            setRevertResult(null);
            setForceRevert(false);
          }}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 hover:text-cyan-200 border border-white/10 font-mono text-xs transition-colors"
        >
          <RotateCcw size={12} />
          <span>Inspect &amp; Undo</span>
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">
              Immutable Audit Ledger &amp; Rollback Cockpit
            </h2>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-xs font-mono font-semibold">
              <ShieldCheck size={13} />
              Append-Only Ledger
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Tamper-resistant audit trail of all capability checks, authorization decisions, and side-effect snapshots
          </p>
        </div>

        {/* Tab Switcher & Refresh */}
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg bg-slate-900 border border-white/10 p-0.5 font-mono text-xs">
            <button
              onClick={() => setActiveTab("AUDIT_EVENTS")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
                activeTab === "AUDIT_EVENTS"
                  ? "bg-slate-700 text-white font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <History size={13} />
              Audit Events
            </button>
            <button
              onClick={() => setActiveTab("SNAPSHOTS")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
                activeTab === "SNAPSHOTS"
                  ? "bg-cyan-500/20 text-cyan-300 font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <RotateCcw size={13} />
              Action Snapshots ({snapshots.length})
            </button>
          </div>

          <button
            onClick={activeTab === "AUDIT_EVENTS" ? fetchAuditLogs : fetchSnapshots}
            disabled={isLoading || snapshotsLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-white/10 font-mono text-xs transition-colors"
          >
            <RefreshCw size={13} className={(isLoading || snapshotsLoading) ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {activeTab === "AUDIT_EVENTS" ? (
        <>
          {/* Filter Controls for Audit Logs */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 font-mono text-xs text-slate-400">
              <Filter size={13} />
              <select
                value={riskFilter}
                aria-label="Filter audit records by risk level"
                onChange={(e) => setRiskFilter(e.target.value)}
                className="bg-slate-900 border border-white/10 text-slate-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="ALL">All Risk Tiers</option>
                <option value="LOW">LOW Risk</option>
                <option value="MEDIUM">MEDIUM Risk</option>
                <option value="HIGH">HIGH Risk</option>
                <option value="CRITICAL">CRITICAL Risk</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 font-mono text-xs text-slate-400">
              <select
                value={statusFilter}
                aria-label="Filter audit records by status"
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-900 border border-white/10 text-slate-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="BLOCKED">BLOCKED</option>
                <option value="DENIED">DENIED</option>
              </select>
            </div>
          </div>

          {/* Audit Data Table */}
          <DataTable
            columns={auditColumns}
            data={logs}
            keyExtractor={(item) => item.event_id}
            searchableKey="tool_name"
            searchPlaceholder="Filter audit records by capability or tool..."
          />
        </>
      ) : (
        /* Action Snapshots Table */
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5 font-mono text-xs text-slate-400 flex items-center justify-between">
            <span>
              Pre-execution snapshots capture complete state snapshots prior to mutating operations with drift detection.
            </span>
            <span className="text-cyan-400 font-semibold">{snapshots.length} Snapshots recorded</span>
          </div>

          <DataTable
            columns={snapshotColumns}
            data={snapshots}
            keyExtractor={(item) => item.id}
            searchableKey="target_path"
            searchPlaceholder="Filter snapshots by target resource path..."
          />
        </div>
      )}

      {/* Revert Modal */}
      {selectedSnapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl max-w-3xl w-full p-6 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <RotateCcw className="text-cyan-400" size={18} />
                <h3 className="font-bold text-white text-base">Snapshot Revert &amp; Rollback Preview</h3>
              </div>
              <button
                onClick={() => setSelectedSnapshot(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-white/5 space-y-1">
                <span className="text-slate-500 uppercase text-[10px] block">Target Resource</span>
                <span className="text-cyan-300 font-semibold truncate block">{selectedSnapshot.target_path || "N/A"}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-white/5 space-y-1">
                <span className="text-slate-500 uppercase text-[10px] block">Reversibility Status</span>
                <span className={selectedSnapshot.is_reversible ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                  {selectedSnapshot.is_reversible ? "Reversible Action" : "Non-Reversible (Permanent)"}
                </span>
              </div>
            </div>

            {selectedSnapshot.diff_patch && (
              <div className="space-y-1.5">
                <span className="text-slate-400 text-xs flex items-center gap-1.5">
                  <FileCode size={14} className="text-cyan-400" />
                  Recorded Unified Diff Patch:
                </span>
                <DiffViewer
                  rawDiff={selectedSnapshot.diff_patch}
                  filePath={selectedSnapshot.target_path || "resource"}
                />
              </div>
            )}

            {revertResult && (
              <div
                className={`p-3 rounded-lg text-xs flex items-start gap-2 border ${
                  revertResult.success
                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    : "bg-rose-500/10 text-rose-300 border-rose-500/30"
                }`}
              >
                {revertResult.success ? (
                  <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-bold">{revertResult.success ? "Success" : "Error"}: </span>
                  {revertResult.message}
                </div>
              </div>
            )}

            <div className="border-t border-white/10 pt-4 flex flex-wrap items-center justify-between gap-4">
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={forceRevert}
                  onChange={(e) => setForceRevert(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0"
                />
                <span>Force Rollback (Bypass state drift detection if file modified)</span>
              </label>

              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => setSelectedSnapshot(null)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Close
                </button>
                <button
                  onClick={handleRevert}
                  disabled={isReverting || !selectedSnapshot.is_reversible || selectedSnapshot.status === "REVERTED"}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-700 text-slate-950 disabled:text-slate-400 text-xs font-bold transition-colors shadow-md shadow-cyan-500/20"
                >
                  <RotateCcw size={14} className={isReverting ? "animate-spin" : ""} />
                  {isReverting ? "Rolling back..." : selectedSnapshot.status === "REVERTED" ? "Already Reverted" : "Revert Action"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
