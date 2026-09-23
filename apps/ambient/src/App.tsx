import React, { useState, useEffect, useRef, useCallback } from "react";
import "./index.css";
import type { AmbientContextState } from "@nexus/types";
import { getFrontmostApp, getSelectedText, hideHud, toggleHud } from "./tauri/bridge";
import { useNexusWebSocket } from "./hooks/useNexusWebSocket";
import { ContextPill } from "./components/ContextPill";
import { PlanningView } from "./components/PlanningView";
import { ToolActivityPulse } from "./components/ToolActivityPulse";
import { InlineApprovalModal } from "./components/InlineApprovalModal";
import { ResultView } from "./components/ResultView";
import { ProactiveAlertPill } from "./components/ProactiveAlertPill";

type HudState = "idle" | "planning" | "executing" | "approval" | "result" | "error";

export default function App() {
  const [query, setQuery] = useState("");
  const [hudState, setHudState] = useState<HudState>("idle");
  const [context, setContext] = useState<AmbientContextState | null>(null);
  const [contextAttached, setContextAttached] = useState(true);
  const [selectedText, setSelectedText] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [apiToken, setApiToken] = useState<string>("");

  const inputRef = useRef<HTMLInputElement>(null);

  // Real-time WebSocket bridge
  const {
    status: wsStatus,
    activePlan,
    activeTool,
    pendingApproval,
    setPendingApproval,
    resultMessage,
    setResultMessage,
  } = useNexusWebSocket();

  // Refresh active macOS context
  const refreshContext = useCallback(async () => {
    try {
      const nativeContext = await getFrontmostApp();
      setContext({
        appName: nativeContext.appName,
        windowTitle: nativeContext.windowTitle,
        capturedAt: new Date().toISOString(),
      });
    } catch {
      setContext({
        appName: "Unknown",
        windowTitle: "",
        capturedAt: new Date().toISOString(),
      });
    }
  }, []);

  // Capture selection explicitly
  const captureSelection = useCallback(async () => {
    try {
      const text = await getSelectedText();
      setSelectedText(text ? text.trim() : null);
    } catch {
      setSelectedText(null);
    }
  }, []);

  // Initial detection & token setup
  useEffect(() => {
    refreshContext();
    const storedToken = localStorage.getItem("nexus_token") || "";
    setApiToken(storedToken);
  }, [refreshContext]);

  // Sync state transitions with WebSocket events
  useEffect(() => {
    if (pendingApproval) {
      setHudState("approval");
    } else if (resultMessage) {
      setHudState("result");
    } else if (activeTool) {
      setHudState("executing");
    } else if (activePlan.length > 0) {
      const allCompleted = activePlan.every((s) => s.status === "completed");
      if (allCompleted && !resultMessage) {
        setHudState("result");
      } else {
        setHudState("planning");
      }
    }
  }, [pendingApproval, resultMessage, activeTool, activePlan]);

  // Safeguard 3: Granular Escape & Dismissal Behavior
  const handleHideHud = useCallback(async () => {
    await hideHud();
  }, []);

  const handleResolveApproval = useCallback(
    async (decision: "approve_once" | "approve_session" | "deny") => {
      if (!pendingApproval) return;
      try {
        const res = await fetch(
          `http://localhost:8000/api/v1/policy/approvals/${pendingApproval.id}/resolve`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
            },
            body: JSON.stringify({ decision }),
          }
        );
        if (!res.ok) {
          throw new Error(`Failed to resolve approval: ${res.statusText}`);
        }
        setPendingApproval(null);
        setHudState("executing");
      } catch (err: any) {
        setErrorMessage(err.message || "Approval resolution failed");
      }
    },
    [pendingApproval, apiToken, setPendingApproval]
  );

  // Global Keyboard Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Global shortcut toggle: Cmd+Shift+Space
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === "Space") {
        e.preventDefault();
        toggleHud();
        refreshContext();
        setTimeout(() => inputRef.current?.focus(), 50);
        return;
      }

      // Safeguard 3: Differentiate Escape behavior based on HUD state
      if (e.key === "Escape") {
        e.preventDefault();
        if (hudState === "approval" && pendingApproval) {
          // Explicit action denial with fallback
          handleResolveApproval("deny");
        } else if (hudState === "executing") {
          // Hide HUD while background execution continues uninterrupted
          handleHideHud();
        } else {
          // In idle or result state: immediately hide HUD window
          handleHideHud();
        }
      }

      // Copy result on Cmd+Enter / Ctrl+Enter in result view
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && hudState === "result" && resultMessage) {
        e.preventDefault();
        navigator.clipboard.writeText(resultMessage);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hudState, pendingApproval, handleResolveApproval, handleHideHud, refreshContext, resultMessage]);

  // Submit Prompt to Agent Orchestrator
  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setErrorMessage(null);
    setResultMessage(null);
    setHudState("planning");

    const contextPayload: Record<string, any> = {};
    if (contextAttached && context) {
      contextPayload.app_name = context.appName;
      contextPayload.window_title = context.windowTitle;
    }
    if (selectedText) {
      contextPayload.selected_text = selectedText;
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/agents/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Client-Surface": "ambient",
          ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
        },
        body: JSON.stringify({
          goal: query.trim(),
          context: Object.keys(contextPayload).length > 0 ? contextPayload : null,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Agent execution failed (${res.status})`);
      }

      const data = await res.json();
      if (data.final_result) {
        setResultMessage(data.final_result);
        setHudState("result");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to communicate with NEXUS core");
      setHudState("error");
    }
  };

  const handleNewQuery = () => {
    setQuery("");
    setResultMessage(null);
    setErrorMessage(null);
    setHudState("idle");
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  return (
    <div className="ambient-container">
      <div className="capsule">
        {/* Unified Search & Prompt Bar */}
        <form onSubmit={handleSubmit} className="input-row">
          <span style={{ color: "#38bdf8", fontSize: "16px", fontWeight: "bold" }}>✦</span>
          <input
            ref={inputRef}
            type="text"
            className="input-field"
            placeholder="Summon NEXUS... (e.g., Run test suite, summarize doc, create file)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <ContextPill
            context={context}
            attached={contextAttached}
            onToggleAttached={() => setContextAttached((prev) => !prev)}
            onRefresh={refreshContext}
            selectedText={selectedText}
            onCaptureSelection={captureSelection}
          />
          {pendingApproval && (
            <ProactiveAlertPill
              hasAlert={true}
              alertText="Intervention Required"
              onClick={() => setHudState("approval")}
            />
          )}
        </form>

        {/* Dynamic State Views */}
        {(hudState !== "idle" || activeTool) && (
          <div className="hud-content">
            {/* Active Tool Activity Pulse */}
            {activeTool && <ToolActivityPulse activity={activeTool} />}

            {/* Inline Approval Request Card */}
            {hudState === "approval" && pendingApproval && (
              <InlineApprovalModal
                approval={pendingApproval}
                onResolve={handleResolveApproval}
              />
            )}

            {/* Planning State (DAG Steps) */}
            {(hudState === "planning" || hudState === "executing") && !pendingApproval && (
              <PlanningView steps={activePlan} />
            )}

            {/* Result View */}
            {hudState === "result" && resultMessage && (
              <ResultView
                content={resultMessage}
                onCopy={() => navigator.clipboard.writeText(resultMessage)}
                onFollowUp={(followUpQuery) => {
                  setQuery(followUpQuery);
                  handleSubmit();
                }}
                onNewQuery={handleNewQuery}
              />
            )}

            {/* Error Message */}
            {hudState === "error" && errorMessage && (
              <div style={{ color: "#f87171", fontSize: "13px", padding: "8px 0" }}>
                ✕ {errorMessage}
              </div>
            )}
          </div>
        )}

        {/* Footer Status Bar */}
        <div className="status-row">
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: wsStatus === "connected" ? "#22c55e" : "#eab308",
              }}
            />
            <span>{wsStatus === "connected" ? "Connected" : "Reconnecting"}</span>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <span>
              <span className="shortcut-badge">↵</span> Execute
            </span>
            <span>
              <span className="shortcut-badge">Esc</span> Hide
            </span>
            <span>
              <span className="shortcut-badge">⌘⇧Space</span> Summon
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
