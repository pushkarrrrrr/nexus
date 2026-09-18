"use client";

import React, { useState } from "react";
import { mockApprovals } from "../../src/mockData/mockApprovals";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { DiffViewer } from "../../src/components/ui/DiffViewer";
import { EmptyState } from "../../src/components/ui/EmptyState";
import type { ApprovalRequest, ApprovalDecisionType } from "@nexus/types";
import { ShieldAlert, CheckCircle2, XCircle, Clock } from "lucide-react";

export default function ApprovalsPage() {
  const [requests, setRequests] = useState<ApprovalRequest[]>(mockApprovals);
  const [resolvedMessage, setResolvedMessage] = useState<string | null>(null);

  const handleDecision = (
    approvalId: string,
    decision: ApprovalDecisionType,
    toolName: string
  ) => {
    setRequests((prev) => prev.filter((r) => r.approval_id !== approvalId));
    setResolvedMessage(
      `Action ${approvalId} [${toolName}] was successfully resolved with verdict: ${decision.toUpperCase()}`
    );
    setTimeout(() => setResolvedMessage(null), 5000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">
              Human-in-the-Loop Approvals
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold">
              {requests.length} PENDING
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Concrete action gating with verified diff previews • Zero blind approvals
          </p>
        </div>
      </div>

      {/* Resolved Toast Notification */}
      {resolvedMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
          <CheckCircle2 size={16} className="shrink-0" />
          <span>{resolvedMessage}</span>
        </div>
      )}

      {/* Pending Approvals List */}
      {requests.length === 0 ? (
        <EmptyState
          icon="🛡️"
          title="Zero Pending Approvals"
          description="All agent actions have been evaluated or approved. The Policy Engine is currently in calm state."
        />
      ) : (
        <div className="space-y-6">
          {requests.map((req) => (
            <Card
              key={req.approval_id}
              title={
                <div className="flex items-center gap-2">
                  <ShieldAlert size={18} className="text-amber-400" />
                  <span className="font-mono text-sm">{req.tool_name}</span>
                </div>
              }
              badge={<StatusBadge risk={req.risk_level} />}
              subtitle={`Approval ID: ${req.approval_id} • Agent: ${req.agent_name} • Session: ${req.session_id}`}
            >
              <div className="space-y-4 font-mono text-xs">
                {/* Reason */}
                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Agent Justification
                  </span>
                  <div className="p-3 rounded-lg bg-slate-900 border border-white/5 text-slate-200">
                    {req.reason}
                  </div>
                </div>

                {/* Diff Viewer if mutating file */}
                {req.diff_preview && (
                  <div>
                    <span className="text-slate-500 uppercase text-[10px] block mb-1">
                      Proposed Code Modification (Diff Preview)
                    </span>
                    <DiffViewer diff={req.diff_preview} />
                  </div>
                )}

                {/* Command Arguments if terminal execution */}
                {req.command_args && (
                  <div>
                    <span className="text-slate-500 uppercase text-[10px] block mb-1">
                      Execution Payload
                    </span>
                    <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                      {JSON.stringify(req.command_args, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center justify-end gap-2.5 pt-3 border-t border-white/5">
                  <button
                    onClick={() => handleDecision(req.approval_id, "deny", req.tool_name)}
                    className="px-3.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium transition-colors"
                  >
                    Deny
                  </button>
                  {req.action_type === "READ" && (
                    <button
                      onClick={() =>
                        handleDecision(req.approval_id, "always_allow_read", req.tool_name)
                      }
                      className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-white/10 font-medium transition-colors"
                    >
                      Always Allow Read
                    </button>
                  )}
                  <button
                    onClick={() =>
                      handleDecision(req.approval_id, "approve_session", req.tool_name)
                    }
                    className="px-3.5 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 font-medium transition-colors"
                  >
                    Approve for Session
                  </button>
                  <button
                    onClick={() =>
                      handleDecision(req.approval_id, "approve_once", req.tool_name)
                    }
                    className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold transition-colors shadow-md shadow-cyan-500/20"
                  >
                    Approve Once
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
