import React from "react";
import type { PlanStep } from "@nexus/types";

interface PlanningViewProps {
  steps: PlanStep[];
}

export const PlanningView: React.FC<PlanningViewProps> = ({ steps }) => {
  if (!steps || steps.length === 0) {
    return (
      <div style={{ color: "#64748b", fontSize: "12px", padding: "10px 0" }}>
        Decomposing task into DAG execution steps...
      </div>
    );
  }

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "completed":
        return <span style={{ color: "#22c55e", fontWeight: "bold" }}>✓</span>;
      case "running":
      case "executing":
        return <span style={{ color: "#38bdf8", animation: "spin 1s linear infinite" }}>◐</span>;
      case "awaiting_approval":
        return <span style={{ color: "#f59e0b", fontWeight: "bold" }}>⚠</span>;
      case "failed":
        return <span style={{ color: "#ef4444", fontWeight: "bold" }}>✕</span>;
      default:
        return <span style={{ color: "#64748b" }}>○</span>;
    }
  };

  return (
    <div className="planning-step-list">
      <div
        style={{
          fontSize: "11px",
          color: "#94a3b8",
          fontFamily: "monospace",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "4px",
        }}
      >
        Execution DAG ({steps.filter((s) => s.status === "completed").length}/{steps.length})
      </div>
      {steps.map((step) => {
        const isRunning = step.status === "running" || step.status === "executing";
        const isAwaiting = step.status === "awaiting_approval";
        const isDone = step.status === "completed";
        const isFailed = step.status === "failed";

        let className = "step-item";
        if (isRunning) className += " running";
        else if (isAwaiting) className += " awaiting_approval";
        else if (isDone) className += " completed";
        else if (isFailed) className += " failed";

        return (
          <div key={step.id} className={className}>
            <div style={{ display: "flex", alignItems: "center", width: "16px", justifyContent: "center" }}>
              {getStatusIcon(step.status)}
            </div>
            <div style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
              <span style={{ fontWeight: 500 }}>{step.description}</span>
              {step.required_tools && step.required_tools.length > 0 && (
                <span
                  style={{
                    marginLeft: "8px",
                    fontSize: "10px",
                    fontFamily: "monospace",
                    color: "#38bdf8",
                    background: "rgba(56, 189, 248, 0.12)",
                    padding: "1px 6px",
                    borderRadius: "4px",
                  }}
                >
                  {step.required_tools.join(", ")}
                </span>
              )}
            </div>
            {step.assigned_agent && (
              <span
                style={{
                  fontSize: "10px",
                  color: "#64748b",
                  fontFamily: "monospace",
                }}
              >
                @{step.assigned_agent}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};
