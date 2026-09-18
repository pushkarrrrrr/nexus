import { useState, useEffect } from "react";
import "./index.css";

export default function App() {
  const [query, setQuery] = useState("");
  const [isVisible, setIsVisible] = useState(true);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [lastEvent, setLastEvent] = useState<string>("Ready for global summon.");

  useEffect(() => {
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket("ws://localhost:8000/ws/nexus?client_surface=ambient");
      setWsStatus("connecting");

      ws.onopen = () => {
        setWsStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setLastEvent(`${parsed.event_type}: ${JSON.stringify(parsed.payload)}`);
        } catch {
          setLastEvent(event.data);
        }
      };

      ws.onerror = () => setWsStatus("disconnected");
      ws.onclose = () => setWsStatus("disconnected");
    } catch {
      setWsStatus("disconnected");
    }

    // Global shortcut listener (Cmd+Shift+Space or Escape to close)
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsVisible(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === "Space") {
        setIsVisible((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (ws) ws.close();
    };
  }, []);

  if (!isVisible) {
    return (
      <div style={{ position: "fixed", bottom: 20, right: 20 }}>
        <button
          onClick={() => setIsVisible(true)}
          style={{
            padding: "8px 14px",
            borderRadius: "20px",
            background: "#0f172a",
            color: "#38bdf8",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            cursor: "pointer",
            fontSize: "12px",
            fontFamily: "monospace",
          }}
        >
          Summon NEXUS (⌘⇧Space)
        </button>
      </div>
    );
  }

  return (
    <div className="ambient-container">
      <div className="capsule">
        <div className="input-row">
          <span style={{ color: "#38bdf8", fontSize: "18px", fontWeight: "bold" }}>✦</span>
          <input
            type="text"
            className="input-field"
            placeholder="Summon NEXUS... (e.g., Run test suite, refactor auth, find papers)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <button
            onClick={() => setIsVisible(false)}
            style={{
              background: "transparent",
              border: "none",
              color: "#64748b",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            ✕
          </button>
        </div>

        <div className="event-ticker">
          <span style={{ color: "#38bdf8", marginRight: "8px" }}>●</span>
          {lastEvent}
        </div>

        <div className="status-row">
          <span>Surface: AMBIENT HUD</span>
          <span>Core Event Bus: <strong style={{ color: wsStatus === "connected" ? "#10b981" : "#f59e0b" }}>{wsStatus.toUpperCase()}</strong></span>
          <span>Hotkey: ⌘⇧Space</span>
        </div>
      </div>
    </div>
  );
}
