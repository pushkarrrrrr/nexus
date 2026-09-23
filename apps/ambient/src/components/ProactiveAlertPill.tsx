import React from "react";

interface ProactiveAlertPillProps {
  hasAlert: boolean;
  alertText?: string;
  onClick?: () => void;
}

export const ProactiveAlertPill: React.FC<ProactiveAlertPillProps> = ({
  hasAlert,
  alertText = "Proactive Watcher Alert",
  onClick,
}) => {
  if (!hasAlert) return null;

  return (
    <div
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "3px 9px",
        borderRadius: "9999px",
        background: "rgba(245, 158, 11, 0.15)",
        border: "1px solid rgba(245, 158, 11, 0.4)",
        color: "#fcd34d",
        fontSize: "11px",
        fontFamily: "monospace",
        fontWeight: 600,
        cursor: "pointer",
        transition: "all 0.2s ease",
      }}
      title="Click to review proactive trigger intervention"
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: "#f59e0b",
          boxShadow: "0 0 8px #f59e0b",
        }}
      />
      <span>⚡ {alertText}</span>
    </div>
  );
};
