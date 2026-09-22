import React from "react";
import type { ApprovalRequestRecord } from "@nexus/types";

interface InlineApprovalModalProps {
  approval: ApprovalRequestRecord;
  onResolve: (decision: "approve_once" | "approve_session" | "deny") => void;
}

export const InlineApprovalModal: React.FC<InlineApprovalModalProps> = ({
  approval,
  onResolve,
}) => {
  const diffLines = approval.diff_preview ? approval.diff_preview.split("\n") : [];

  return (
    <div className="approval-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "16px" }}>⚠️</span>
          <span style={{ fontWeight: 600, fontSize: "14px", color: "#f59e0b" }}>
            Authorization Required
          </span>
        </div>
        <div style={{ display: "flex", gap: "6px" }}>
          <span
            style={{
              fontSize: "10px",
              fontFamily: "monospace",
              padding: "2px 8px",
              borderRadius: "4px",
              background: "rgba(245, 158, 11, 0.2)",
              color: "#fbbf24",
              border: "1px solid rgba(245, 158, 11, 0.4)",
            }}
          >
            {approval.risk_level} RISK
          </span>
          <span
            style={{
              fontSize: "10px",
              fontFamily: "monospace",
              padding: "2px 8px",
              borderRadius: "4px",
              background: approval.is_reversible ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)",
              color: approval.is_reversible ? "#86efac" : "#fca5a5",
              border: `1px solid ${approval.is_reversible ? "rgba(34, 197, 94, 0.4)" : "rgba(239, 68, 68, 0.4)"}`,
            }}
          >
            {approval.is_reversible ? "↺ Reversible" : "⚡ Permanent"}
          </span>
        </div>
      </div>

      <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
        <strong>Capability:</strong> <code style={{ color: "#38bdf8" }}>{approval.capability_name}</code>
      </div>

      {approval.affected_resources && approval.affected_resources.length > 0 && (
        <div style={{ fontSize: "12px", color: "#94a3b8" }}>
          <strong>Target:</strong> {approval.affected_resources.join(", ")}
        </div>
      )}

      <div style={{ fontSize: "12px", color: "#e2e8f0" }}>
        {approval.reason}
      </div>

      {approval.diff_preview && (
        <div className="diff-box">
          {diffLines.map((line, idx) => {
            let className = "";
            if (line.startsWith("+") && !line.startsWith("+++")) className = "diff-add";
            else if (line.startsWith("-") && !line.startsWith("---")) className = "diff-del";
            return (
              <div key={idx} className={className}>
                {line}
              </div>
            );
          })}
        </div>
      )}

      <div className="btn-row">
        <button
          className="btn-danger"
          onClick={() => onResolve("deny")}
          title="Deny action (Esc)"
        >
          Deny (Esc)
        </button>
        <button
          className="btn-primary"
          style={{ background: "#475569", color: "#f8fafc" }}
          onClick={() => onResolve("approve_session")}
          title="Approve for this session"
        >
          Approve Session
        </button>
        <button
          className="btn-primary"
          onClick={() => onResolve("approve_once")}
          title="Approve single execution (Enter)"
        >
          Approve Once (↵)
        </button>
      </div>
    </div>
  );
};
