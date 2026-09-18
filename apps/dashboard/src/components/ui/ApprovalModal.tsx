import React, { useState } from "react";
import type { ApprovalRequest, ApprovalDecisionType } from "@nexus/types";
import { StatusBadge } from "./StatusBadge";
import { DiffViewer } from "./DiffViewer";

interface ApprovalModalProps {
  request: ApprovalRequest;
  onDecision: (approvalId: string, decision: ApprovalDecisionType, notes?: string) => void;
  onClose?: () => void;
}

export function ApprovalModal({ request, onDecision, onClose }: ApprovalModalProps) {
  const [notes, setNotes] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-150">
      <div className="w-full max-w-2xl glass-panel rounded-2xl border border-white/15 shadow-2xl overflow-hidden text-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/60">
          <div className="flex items-center gap-3">
            <span className="text-amber-400 text-lg">⚠️</span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white tracking-tight">
                  Action Approval Required
                </h3>
                <StatusBadge risk={request.risk_level} />
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                ID: {request.approval_id} • Agent: {request.agent_name}
              </p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white text-sm p-1 transition-colors"
            >
              ✕
            </button>
          )}
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Reason & Intent */}
          <div>
            <span className="text-xs font-mono uppercase text-slate-400 block mb-1">
              Agent Proposed Intent:
            </span>
            <div className="p-3 rounded-lg bg-slate-900/80 border border-white/5 text-sm text-slate-200">
              {request.reason}
            </div>
          </div>

          {/* Tool & Command Details */}
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded bg-slate-900/50 border border-white/5">
              <span className="text-slate-500 block">Target Capability</span>
              <span className="text-cyan-400 font-semibold">{request.tool_name}</span>
            </div>
            <div className="p-2.5 rounded bg-slate-900/50 border border-white/5">
              <span className="text-slate-500 block">Action Type</span>
              <span className="text-amber-300 font-semibold">{request.action_type}</span>
            </div>
          </div>

          {/* Diff Preview if present */}
          {request.diff_preview && (
            <div>
              <span className="text-xs font-mono uppercase text-slate-400 block mb-1.5">
                Proposed State Mutation (Unified Diff):
              </span>
              <DiffViewer diff={request.diff_preview} />
            </div>
          )}

          {/* Optional notes input */}
          {showNotes && (
            <div>
              <label className="text-xs font-mono uppercase text-slate-400 block mb-1">
                Feedback / Denial Reason (Returned to Agent):
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Explain why this action was modified or rejected..."
                className="w-full h-20 p-2.5 rounded-lg bg-slate-950 border border-white/10 text-xs font-mono text-white outline-none focus:border-cyan-500"
              />
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-white/10 bg-slate-950/60">
          <button
            type="button"
            onClick={() => setShowNotes(!showNotes)}
            className="text-xs font-mono text-slate-400 hover:text-slate-200 underline"
          >
            {showNotes ? "Hide notes" : "+ Add feedback note"}
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onDecision(request.approval_id, "deny", notes)}
              className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-mono font-medium transition-colors"
            >
              Deny
            </button>
            {request.action_type === "READ" && (
              <button
                onClick={() => onDecision(request.approval_id, "always_allow_read")}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-white/10 text-xs font-mono font-medium transition-colors"
              >
                Always Allow Read
              </button>
            )}
            <button
              onClick={() => onDecision(request.approval_id, "approve_session")}
              className="px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 text-xs font-mono font-medium transition-colors"
            >
              Approve for Session
            </button>
            <button
              onClick={() => onDecision(request.approval_id, "approve_once")}
              className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-semibold text-xs transition-colors shadow-lg shadow-cyan-500/20"
            >
              Approve Once
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
