"use client";

import React, { useState, useEffect, useCallback } from "react";
import { mockApprovals } from "../../src/mockData/mockApprovals";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { DiffViewer } from "../../src/components/ui/DiffViewer";
import { EmptyState } from "../../src/components/ui/EmptyState";
import { useAuth } from "../../src/context/AuthContext";
import type { RiskLevel, ActionType } from "@nexus/types";
import { ShieldAlert, CheckCircle2, RefreshCw, Layers, ShieldCheck } from "lucide-react";

interface ApprovalItem {
  id: string;
  capability_name: string;
  action_category: ActionType | string;
  risk_level: RiskLevel;
  reason: string;
  affected_resources: string[];
  parameters: Record<string, unknown>;
  status: string;
  expires_at?: string | null;
  created_at: string;
  task_id?: string | null;
  step_id?: string | null;
  diff_preview?: {
    file_path: string;
    unified_diff: string;
    lines_added: number;
    lines_removed: number;
  } | string | null;
  snapshot_id?: string | null;
  is_reversible?: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ApprovalsPage() {
  const { token } = useAuth();
  const [requests, setRequests] = useState<ApprovalItem[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("PENDING");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [resolvedMessage, setResolvedMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const url = filterStatus === "ALL"
        ? `${API_BASE}/api/v1/policy/approvals`
        : `${API_BASE}/api/v1/policy/approvals?status=${filterStatus}`;

      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        const data = await res.json();
        if (data.items && Array.isArray(data.items)) {
          setRequests(data.items);
          setIsLoading(false);
          return;
        }
      }
      throw new Error("Using fallback mock approvals");
    } catch {
      // Fallback to mock data
      const mappedMocks: ApprovalItem[] = mockApprovals.map((m) => ({
        id: m.approval_id,
        capability_name: m.tool_name,
        action_category: m.action_type,
        risk_level: m.risk_level,
        reason: m.reason,
        affected_resources: m.diff_preview ? [m.diff_preview.file_path] : [],
        parameters: m.command_args || {},
        status: "PENDING",
        expires_at: m.expires_at || null,
        created_at: m.created_at,
        diff_preview: m.diff_preview,
      }));
      setRequests(mappedMocks);
    } finally {
      setIsLoading(false);
    }
  }, [token, filterStatus]);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleDecision = async (
    approvalId: string,
    decision: "APPROVED" | "DENIED",
    scope: "ONE_TIME" | "SESSION" | "STANDING",
    capabilityName: string
  ) => {
    setErrorMessage(null);
    try {
      if (token) {
        const res = await fetch(`${API_BASE}/api/v1/policy/approvals/${approvalId}/resolve`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            decision,
            chosen_scope: scope,
            session_ttl_minutes: 60,
          }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to resolve approval.");
        }
      }

      setRequests((prev) => prev.filter((r) => r.id !== approvalId));
      setResolvedMessage(
        `Action '${approvalId}' [${capabilityName}] successfully ${decision} (Scope: ${scope}).`
      );
      setTimeout(() => setResolvedMessage(null), 5000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resolve approval.";
      setErrorMessage(msg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const getRiskBadgeColor = (risk: RiskLevel) => {
    switch (risk) {
      case "LOW":
        return "bg-blue-500/15 text-blue-300 border-blue-500/30";
      case "MEDIUM":
        return "bg-amber-500/15 text-amber-300 border-amber-500/30";
      case "HIGH":
        return "bg-orange-500/15 text-orange-300 border-orange-500/30";
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">
              Human-in-the-Loop Approvals &amp; Security Cockpit
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-bold">
              {requests.filter((r) => r.status === "PENDING").length} PENDING
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Granular capability gating with resource boundaries • Zero blind approvals
          </p>
        </div>

        {/* Filter & Refresh */}
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg bg-slate-900 border border-white/10 p-0.5 font-mono text-xs">
            <button
              onClick={() => setFilterStatus("PENDING")}
              className={`px-3 py-1 rounded-md transition-colors ${
                filterStatus === "PENDING"
                  ? "bg-amber-500/20 text-amber-300 font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Pending
            </button>
            <button
              onClick={() => setFilterStatus("ALL")}
              className={`px-3 py-1 rounded-md transition-colors ${
                filterStatus === "ALL"
                  ? "bg-slate-700 text-white font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              All History
            </button>
          </div>

          <button
            onClick={fetchApprovals}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-white/10 font-mono text-xs transition-colors"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Notifications */}
      {resolvedMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
          <CheckCircle2 size={16} className="shrink-0" />
          <span>{resolvedMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center gap-2">
          <ShieldAlert size={16} className="shrink-0" />
          <span>{errorMessage}</span>
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
          {requests.map((req) => {
            const isLowRiskRead =
              req.risk_level === "LOW" && req.action_category === "READ";
            const isPending = req.status === "PENDING";

            return (
              <Card
                key={req.id}
                title={
                  <div className="flex flex-wrap items-center gap-2.5">
                    <ShieldAlert size={18} className="text-amber-400 shrink-0" />
                    <span className="font-mono text-sm text-white font-semibold">
                      {req.capability_name}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                      {req.action_category}
                    </span>
                    {req.is_reversible !== undefined && (
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono border flex items-center gap-1 ${
                          req.is_reversible
                            ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        }`}
                      >
                        {req.is_reversible ? "↺ Reversible [Undo supported]" : "⚠ Non-Reversible [Permanent]"}
                      </span>
                    )}
                  </div>
                }
                badge={
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2.5 py-0.5 rounded-full border text-[11px] font-mono font-bold ${getRiskBadgeColor(
                        req.risk_level
                      )}`}
                    >
                      {req.risk_level}
                    </span>
                    {!isPending && (
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono">
                        {req.status}
                      </span>
                    )}
                  </div>
                }
                subtitle={`Approval ID: ${req.id} • Created: ${new Date(
                  req.created_at
                ).toLocaleTimeString()} ${
                  req.expires_at
                    ? `• Expires: ${new Date(req.expires_at).toLocaleTimeString()}`
                    : ""
                }`}
              >
                <div className="space-y-4 font-mono text-xs">
                  {/* Reason */}
                  <div>
                    <span className="text-slate-500 uppercase text-[10px] block mb-1">
                      Policy Evaluation Reason &amp; Agent Intent
                    </span>
                    <div className="p-3 rounded-lg bg-slate-900 border border-white/5 text-slate-200">
                      {req.reason}
                    </div>
                  </div>

                  {/* Affected Resources */}
                  {req.affected_resources && req.affected_resources.length > 0 && (
                    <div>
                      <span className="text-slate-500 uppercase text-[10px] block mb-1">
                        Affected Target Resources
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {req.affected_resources.map((res, i) => (
                          <span
                            key={i}
                            className="px-2.5 py-1 rounded bg-slate-950 border border-cyan-500/30 text-cyan-300 text-[11px]"
                          >
                            {res}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Diff Viewer if mutating file */}
                  {req.diff_preview && (
                    <div>
                      <span className="text-slate-500 uppercase text-[10px] block mb-1">
                        Proposed Code Modification (Diff Preview)
                      </span>
                      {typeof req.diff_preview === "string" ? (
                        <DiffViewer
                          rawDiff={req.diff_preview}
                          filePath={req.affected_resources?.[0] || "file.txt"}
                        />
                      ) : (
                        <DiffViewer diff={req.diff_preview} />
                      )}
                    </div>
                  )}

                  {/* Parameters / Command Arguments */}
                  {req.parameters && Object.keys(req.parameters).length > 0 && (
                    <div>
                      <span className="text-slate-500 uppercase text-[10px] block mb-1">
                        Action Parameters
                      </span>
                      <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                        {JSON.stringify(req.parameters, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Action Buttons */}
                  {isPending && (
                    <div className="flex flex-wrap items-center justify-end gap-2.5 pt-3 border-t border-white/5">
                      <button
                        onClick={() =>
                          handleDecision(
                            req.id,
                            "DENIED",
                            "ONE_TIME",
                            req.capability_name
                          )
                        }
                        className="px-3.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium transition-colors"
                      >
                        Deny
                      </button>

                      {isLowRiskRead && (
                        <button
                          onClick={() =>
                            handleDecision(
                              req.id,
                              "APPROVED",
                              "STANDING",
                              req.capability_name
                            )
                          }
                          title="Standing approval restricted to LOW-risk READ-only capabilities"
                          className="px-3.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 font-medium transition-colors"
                        >
                          Always Allow (Standing)
                        </button>
                      )}

                      <button
                        onClick={() =>
                          handleDecision(
                            req.id,
                            "APPROVED",
                            "SESSION",
                            req.capability_name
                          )
                        }
                        className="px-3.5 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 font-medium transition-colors"
                      >
                        Approve for Session
                      </button>

                      <button
                        onClick={() =>
                          handleDecision(
                            req.id,
                            "APPROVED",
                            "ONE_TIME",
                            req.capability_name
                          )
                        }
                        className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold transition-colors shadow-md shadow-cyan-500/20"
                      >
                        Approve Once
                      </button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
