import { useState, useEffect, useCallback, useRef } from "react";
import "./index.css";
import type { AmbientContextState } from "@nexus/types";
import { getFrontmostApp, hideHud, toggleHud, speakNative } from "./tauri/bridge";
import { useNexusWebSocket } from "./hooks/useNexusWebSocket";
import { VoiceOrb } from "./components/VoiceOrb";
import { sendAmbientChatMessage } from "./services/ambientChatService";

export default function App() {
  const [context, setContext] = useState<AmbientContextState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [apiToken, setApiToken] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);

  // Real-time WebSocket bridge
  const {
    status: wsStatus,
    activeTool,
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

  useEffect(() => {
    refreshContext();
    const storedToken = localStorage.getItem("nexus_token") || "";
    setApiToken(storedToken);
  }, [refreshContext]);

  // Global Keyboard Listener: Cmd+Shift+Space / Cmd+Shift+P to toggle, Esc to hide
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        (e.code === "Space" || e.code === "KeyP" || e.key === "p" || e.key === "P")
      ) {
        e.preventDefault();
        toggleHud();
        refreshContext();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        hideHud();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [refreshContext]);

  const isSpeakingRef = useRef<boolean>(false);
  const isProcessingRef = useRef<boolean>(false);
  const lastProcessedTimeRef = useRef<number>(0);
  const lastTranscriptRef = useRef<string>("");

  // Submit voice prompt to NEXUS core
  const handleVoicePrompt = useCallback(
    async (spokenText: string) => {
      // 1. Acoustic echo guard: ignore speech while NEXUS itself is speaking
      if (isSpeakingRef.current) return;

      // 2. Debounce duplicates: ignore identical speech within 2.5 seconds
      const now = Date.now();
      const clean = spokenText.trim().toLowerCase();
      if (!clean) return;
      if (clean === lastTranscriptRef.current && now - lastProcessedTimeRef.current < 2500) {
        return;
      }
      lastTranscriptRef.current = clean;
      lastProcessedTimeRef.current = now;

      // 3. Concurrency guard
      if (isProcessingRef.current) return;
      isProcessingRef.current = true;
      setIsProcessing(true);
      setErrorMessage(null);

      // Check for standalone greetings ("hello", "hey", "hi", "namaste", etc.)
      const isPureGreeting =
        /^(?:hey|hi|hello|namaste|oye|suno)\s*(?:nexus|nuxus|nexas|nexis)?[!.,?]?$/i.test(clean) ||
        /^(?:nexus|nuxus|nexas|nexis)[!.,?]?$/i.test(clean);
      if (isPureGreeting) {
        setIsSpeaking(true);
        isSpeakingRef.current = true;
        setResultMessage("Hello! How can I help you?");
        await speakNative("Hello! How can I help you?");
        setTimeout(() => {
          setIsSpeaking(false);
          isSpeakingRef.current = false;
        }, 1800);
        isProcessingRef.current = false;
        setIsProcessing(false);
        return;
      }

      // Strip wake word prefix if user asked a question, e.g. "hey nexus, kaise ho?" -> "kaise ho?"
      const cleanGoal =
        clean
          .replace(/^(?:hey|hi|hello|ok|oye|suno)?\s*(?:nexus|nuxus|nexas|nexis|next us|lexus)\s*[!.,?]?\s*/i, "")
          .trim() || clean;

      try {
        const replyText = await sendAmbientChatMessage(
          cleanGoal,
          context ? { app_name: context.appName, window_title: context.windowTitle } : null,
          apiToken
        );

        if (replyText) {
          setResultMessage(replyText);
          setIsSpeaking(true);
          isSpeakingRef.current = true;
          await speakNative(replyText);
          const duration = Math.min(8000, Math.max(1800, replyText.length * 65));
          setTimeout(() => {
            setIsSpeaking(false);
            isSpeakingRef.current = false;
          }, duration);
        }
      } catch (err: any) {
        console.warn("[Ambient] chat error:", err);
        const fallbackText = "Main sun rahi hoon! Boliye, main kya madad karoon?";
        setResultMessage(fallbackText);
        setIsSpeaking(true);
        isSpeakingRef.current = true;
        await speakNative(fallbackText);
        setTimeout(() => {
          setIsSpeaking(false);
          isSpeakingRef.current = false;
        }, 2000);
      } finally {
        isProcessingRef.current = false;
        setIsProcessing(false);
      }
    },
    [apiToken, context]
  );

  const [inputText, setInputText] = useState<string>("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Click on circle triggers greeting & focuses input
  const handleWakeWord = useCallback(async () => {
    if (isSpeakingRef.current) return;
    setIsSpeaking(true);
    isSpeakingRef.current = true;
    setResultMessage("Hello! What would you like me to do?");
    await speakNative("Hello! What would you like me to do?");
    setTimeout(() => {
      setIsSpeaking(false);
      isSpeakingRef.current = false;
      inputRef.current?.focus();
    }, 1400);
  }, []);

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = inputText.trim();
    if (!val) return;
    setInputText("");
    handleVoicePrompt(val);
  };

  return (
    <div className="liquid-glass-container" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <VoiceOrb
        onSpeechEnd={handleVoicePrompt}
        onWakeWord={handleWakeWord}
        statusText={
          errorMessage
            ? `✕ ${errorMessage}`
            : resultMessage
            ? resultMessage.slice(0, 36) + "..."
            : activeTool
            ? `Executing ${activeTool.tool}...`
            : isProcessing
            ? "Processing..."
            : wsStatus === "connected"
            ? undefined
            : "Connecting..."
        }
        isProcessing={isProcessing || !!activeTool}
        isSpeaking={isSpeaking}
      />

      {/* Interactive Command Bar */}
      <form
        className="no-drag"
        onSubmit={handleTextSubmit}
        style={{
          marginTop: "10px",
          display: "flex",
          alignItems: "center",
          background: "rgba(15, 23, 42, 0.8)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          border: "1px solid rgba(56, 189, 248, 0.35)",
          borderRadius: "20px",
          padding: "5px 12px",
          width: "360px",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5), 0 0 12px rgba(56, 189, 248, 0.2)",
        }}
      >
        <input
          ref={inputRef}
          className="no-drag"
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Speak or type command (e.g. scroll down)..."
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#f8fafc",
            fontSize: "12px",
            fontFamily: "inherit",
          }}
        />
        <button
          className="no-drag"
          type="submit"
          style={{
            background: "rgba(56, 189, 248, 0.25)",
            border: "1px solid rgba(56, 189, 248, 0.5)",
            borderRadius: "50%",
            width: "22px",
            height: "22px",
            color: "#38bdf8",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "11px",
            padding: 0,
          }}
        >
          ➔
        </button>
      </form>

      {/* Quick Action Pills */}
      <div
        className="no-drag"
        style={{
          display: "flex",
          gap: "6px",
          marginTop: "6px",
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {[
          { label: "📜 Scroll Down", cmd: "scroll down" },
          { label: "🖥️ Read Screen", cmd: "screen pe kya hai" },
          { label: "🪟 Windows", cmd: "kaun se windows open hai" },
          { label: "🎵 Spotify", cmd: "spotify kholo" },
        ].map((btn) => (
          <button
            key={btn.label}
            className="no-drag"
            type="button"
            onClick={() => handleVoicePrompt(btn.cmd)}
            style={{
              background: "rgba(30, 41, 59, 0.7)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "10px",
              padding: "3px 8px",
              fontSize: "10px",
              color: "#94a3b8",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#38bdf8";
              e.currentTarget.style.borderColor = "rgba(56, 189, 248, 0.4)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.15)";
            }}
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  );
}
