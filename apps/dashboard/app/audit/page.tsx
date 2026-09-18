"use client";

import React, { useState } from "react";
import { mockAuditLogs } from "../../src/mockData/mockAuditLogs";
import { DataTable, type Column } from "../../src/components/ui/DataTable";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { AuditEvent } from "@nexus/types";
import { History, Undo2, ShieldCheck, CheckCircle2 } from "lucide-react";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEvent[]>(mockAuditLogs);
  const [undoMessage, setUndoMessage] = useState<string | null>(null);

  const handleRollback = (eventId: string, snapshotId?: string) => {
    setLogs((prev) =>
      prev.map((l) =>
        l.event_id === eventId
          ? { ...l, undone_at: new Date().toISOString() }
          : l
      )
    );
    setUndoMessage(
      `Successfully rolled back action [${eventId}] using snapshot [${snapshotId || "N/A"}]. State restored.`
    );
    setTimeout(() => setUndoMessage(null), 5000);
  };

  const columns: Column<AuditEvent>[] = [
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
      header: "Time",
      render: (item) => (
        <span className="font-mono text-slate-400 text-[11px]">
          {item.timestamp}
        </span>
      ),
    },
    {
      key: "agent_name",
      header: "Agent",
      render: (item) => (
        <span className="font-mono text-slate-200">{item.agent_name}</span>
      ),
    },
    {
      key: "tool_name",
      header: "Tool & Action",
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
      header: "Verdict",
      render: (item) => (
        <span
          className={`font-mono text-[11px] font-semibold uppercase ${
            item.policy_decision === "blocked_by_policy"
              ? "text-rose-400"
              : item.policy_decision === "approved_by_user"
              ? "text-cyan-400"
              : "text-emerald-400"
          }`}
        >
          {item.policy_decision.replace(/_/g, " ")}
        </span>
      ),
    },
    {
      key: "execution_duration_ms",
      header: "Latency",
      render: (item) => (
        <span className="font-mono text-slate-400 text-[11px]">
          {item.execution_duration_ms}ms
        </span>
      ),
    },
    {
      key: "actions",
      header: "Rollback",
      render: (item) => {
        if (item.undone_at) {
          return (
            <span className="text-[10px] font-mono text-slate-500 line-through">
              ROLLED BACK
            </span>
          );
        }
        if (item.undo_registered && item.snapshot_id) {
          return (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRollback(item.event_id, item.snapshot_id);
              }}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-mono font-bold transition-colors"
            >
              <Undo2 size={11} /> Rollback
            </button>
          );
        }
        return (
          <span className="text-[10px] font-mono text-slate-600">
            N/A
          </span>
        );
      },
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Immutable Audit Ledger &amp; Rollback</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Cryptographically verifiable record of all agent intents, policy verdicts, and snapshots
          </p>
        </div>
      </div>

      {undoMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
          <CheckCircle2 size={16} className="shrink-0" />
          <span>{undoMessage}</span>
        </div>
      )}

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={logs}
        keyExtractor={(item) => item.event_id}
        searchableKey="tool_name"
        searchPlaceholder="Filter audit records by tool name..."
      />
    </div>
  );
}
