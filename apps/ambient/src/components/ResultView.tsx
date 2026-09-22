import React, { useState } from "react";

interface ResultViewProps {
  content: string;
  onCopy: () => void;
  onFollowUp: (query: string) => void;
  onNewQuery: () => void;
}

export const ResultView: React.FC<ResultViewProps> = ({
  content,
  onCopy,
  onFollowUp,
  onNewQuery,
}) => {
  const [followUp, setFollowUp] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFollowUpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (followUp.trim()) {
      onFollowUp(followUp.trim());
      setFollowUp("");
    }
  };

  return (
    <div className="result-box" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          paddingBottom: "6px",
        }}
      >
        <span
          style={{
            fontSize: "11px",
            color: "#94a3b8",
            fontFamily: "monospace",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Response
        </span>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleCopy}
            style={{
              background: "rgba(255, 255, 255, 0.06)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "4px",
              color: copied ? "#86efac" : "#cbd5e1",
              fontSize: "11px",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            {copied ? "✓ Copied" : "Copy (⌘↵)"}
          </button>
          <button
            onClick={onNewQuery}
            style={{
              background: "rgba(255, 255, 255, 0.06)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "4px",
              color: "#cbd5e1",
              fontSize: "11px",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            New Query
          </button>
        </div>
      </div>

      <div
        style={{
          maxHeight: "180px",
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          fontSize: "13px",
          lineHeight: "1.5",
          color: "#f1f5f9",
          padding: "4px 0",
        }}
      >
        {content}
      </div>

      <form onSubmit={handleFollowUpSubmit} style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
        <input
          type="text"
          placeholder="Ask a follow-up query..."
          value={followUp}
          onChange={(e) => setFollowUp(e.target.value)}
          style={{
            flex: 1,
            background: "rgba(0, 0, 0, 0.25)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: "6px",
            padding: "6px 10px",
            color: "#fff",
            fontSize: "12px",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={!followUp.trim()}
          style={{
            background: followUp.trim() ? "#38bdf8" : "#334155",
            color: followUp.trim() ? "#020617" : "#64748b",
            border: "none",
            borderRadius: "6px",
            padding: "6px 12px",
            fontSize: "12px",
            fontWeight: 600,
            cursor: followUp.trim() ? "pointer" : "default",
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};
