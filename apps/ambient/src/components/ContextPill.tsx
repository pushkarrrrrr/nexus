import React from "react";
import type { AmbientContextState } from "@nexus/types";

interface ContextPillProps {
  context: AmbientContextState | null;
  attached: boolean;
  onToggleAttached: () => void;
  onRefresh: () => void;
  selectedText?: string | null;
  onCaptureSelection?: () => void;
}

export const ContextPill: React.FC<ContextPillProps> = ({
  context,
  attached,
  onToggleAttached,
  onRefresh,
  selectedText,
  onCaptureSelection,
}) => {
  if (!context) {
    return (
      <span
        className="context-pill detached"
        onClick={onRefresh}
        title="Click to detect frontmost active application"
      >
        <span style={{ fontSize: "10px" }}>⟳</span> No Context
      </span>
    );
  }

  const label = context.windowTitle
    ? `${context.appName}: ${context.windowTitle}`
    : context.appName;

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
      <span
        className={`context-pill ${attached ? "" : "detached"}`}
        onClick={onToggleAttached}
        title={
          attached
            ? "Context attached to prompt. Click to detach."
            : "Context detached. Click to attach."
        }
      >
        <span style={{ fontSize: "10px" }}>{attached ? "●" : "○"}</span>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", maxWidth: "200px" }}>
          {label}
        </span>
      </span>

      {onCaptureSelection && (
        <span
          className={`context-pill ${selectedText ? "" : "detached"}`}
          onClick={onCaptureSelection}
          style={{ cursor: "pointer", fontSize: "10px", padding: "3px 8px" }}
          title={
            selectedText
              ? `Attached selection (${selectedText.length} chars). Click to re-capture.`
              : "Click to capture currently selected text in frontmost window"
          }
        >
          {selectedText ? `Selection (${selectedText.slice(0, 16)}...)` : "+ Selection"}
        </span>
      )}
    </div>
  );
};
