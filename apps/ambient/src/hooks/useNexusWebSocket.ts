import { useState, useEffect, useRef, useCallback } from "react";
import type { PlanStep, ApprovalRequestRecord } from "@nexus/types";

export interface ToolActivityEvent {
  tool: string;
  target?: string;
  step_id?: string;
  status: "running" | "completed" | "failed";
}

export interface WebSocketEventMessage {
  event_type: string;
  task_id?: string;
  payload?: any;
  timestamp?: string;
}

export function useNexusWebSocket(url = "ws://localhost:8000/ws/nexus?client_surface=ambient") {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [activePlan, setActivePlan] = useState<PlanStep[]>([]);
  const [activeTool, setActiveTool] = useState<ToolActivityEvent | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequestRecord | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setStatus("connecting");

      ws.onopen = () => {
        setStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEventMessage = JSON.parse(event.data);
          
          if (data.event_type === "task_state_changed" && data.payload) {
            if (data.task_id) setActiveTaskId(data.task_id);
            if (data.payload.status === "completed" && data.payload.result) {
              setResultMessage(typeof data.payload.result === "string" ? data.payload.result : JSON.stringify(data.payload.result, null, 2));
              setActiveTool(null);
            }
          }

          if (data.event_type === "plan_updated" && Array.isArray(data.payload?.steps)) {
            setActivePlan(data.payload.steps);
          }

          if (data.event_type === "step_updated" && data.payload?.step) {
            const updated: PlanStep = data.payload.step;
            setActivePlan((prev) =>
              prev.map((s) => (s.id === updated.id ? updated : s))
            );
          }

          if (data.event_type === "tool_activity" && data.payload) {
            setActiveTool({
              tool: data.payload.tool || "terminal.execute",
              target: data.payload.target || "",
              step_id: data.payload.step_id,
              status: data.payload.status || "running",
            });
            if (data.payload.status === "completed" || data.payload.status === "failed") {
              setTimeout(() => setActiveTool(null), 1500);
            }
          }

          if (data.event_type === "approval_required" && data.payload) {
            setPendingApproval(data.payload);
          }

          if (data.event_type === "approval_resolved") {
            setPendingApproval(null);
          }

          if (data.event_type === "agent_message" && data.payload?.content) {
            setResultMessage((prev) => (prev ? `${prev}\n${data.payload.content}` : data.payload.content));
          }
        } catch (err) {
          console.debug("Failed to parse WebSocket message:", err);
        }
      };

      ws.onerror = () => {
        setStatus("disconnected");
      };

      ws.onclose = () => {
        setStatus("disconnected");
        // Reconnect after 3s
        setTimeout(() => {
          if (wsRef.current === ws) {
            connect();
          }
        }, 3000);
      };
    } catch {
      setStatus("disconnected");
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendEvent = useCallback((eventType: string, payload: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event_type: eventType, payload }));
    }
  }, []);

  return {
    status,
    activeTaskId,
    setActiveTaskId,
    activePlan,
    setActivePlan,
    activeTool,
    setActiveTool,
    pendingApproval,
    setPendingApproval,
    resultMessage,
    setResultMessage,
    sendEvent,
  };
}
