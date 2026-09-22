import React from "react";
import type { ToolActivityEvent } from "../hooks/useNexusWebSocket";

interface ToolActivityPulseProps {
  activity: ToolActivityEvent;
}

export const ToolActivityPulse: React.FC<ToolActivityPulseProps> = ({ activity }) => {
  return (
    <div className="tool-pulse">
      <div className="pulse-dot" />
      <div style={{ display: "flex", flexDirection: "column", gap: "2px", overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontWeight: 600, color: "#7dd3fc" }}>{activity.tool}</span>
          <span style={{ fontSize: "10px", color: "#94a3b8" }}>running...</span>
        </div>
        {activity.target && (
          <span
            style={{
              fontSize: "11px",
              color: "#64748b",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            target: {activity.target}
          </span>
        )}
      </div>
    </div>
  );
};
