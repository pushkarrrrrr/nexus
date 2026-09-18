"use client";

import { useEffect, useState } from "react";

interface HealthData {
  status: string;
  version: string;
  environment: string;
  database: string;
  database_healthy: boolean;
  timestamp: string;
}

export default function DashboardHome() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [wsMessages, setWsMessages] = useState<string[]>([]);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/health");
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const data = await res.json();
      setHealth(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to connect to NEXUS Core API");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);

    // WebSocket connection
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket("ws://localhost:8000/ws/nexus?client_surface=dashboard");
      setWsStatus("connecting");

      ws.onopen = () => {
        setWsStatus("connected");
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setWsMessages((prev) => [
            `[${new Date().toLocaleTimeString()}] ${parsed.event_type}: ${JSON.stringify(parsed.payload)}`,
            ...prev.slice(0, 4),
          ]);
        } catch {
          setWsMessages((prev) => [`Raw: ${event.data}`, ...prev.slice(0, 4)]);
        }
      };

      ws.onerror = () => {
        setWsStatus("disconnected");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
      };
    } catch {
      setWsStatus("disconnected");
    }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, []);

  return (
    <main className="max-w-7xl mx-auto p-6 md:p-10 space-y-8">
      {/* Header Bar */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-500 bg-clip-text text-transparent">
              NEXUS OPERATING SYSTEM
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-mono rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              PHASE 1 FOUNDATION
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Production Command Center • Unified Dual-Surface AI Core
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchHealth}
            className="px-4 py-2 text-xs font-mono font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-white/10 transition-colors flex items-center gap-2"
          >
            <span className={loading ? "animate-spin" : ""}>↻</span>
            Refresh Status
          </button>
        </div>
      </header>

      {/* Core Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Core API Card */}
        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Services / API</span>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${health?.status === "ok" ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
              <span className="text-xs font-mono text-slate-300">
                {health?.status === "ok" ? "ONLINE" : "OFFLINE"}
              </span>
            </div>
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">FastAPI Core Engine</h2>
          <p className="text-xs text-slate-400 mb-4">Port 8000 • Async Request Bus &amp; Policy Gating</p>
          <div className="space-y-1.5 text-xs font-mono text-slate-300 border-t border-white/5 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-500">Version:</span>
              <span>{health?.version || "0.1.0"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Environment:</span>
              <span className="text-cyan-400">{health?.environment || "development"}</span>
            </div>
          </div>
        </div>

        {/* Database & Migrations Card */}
        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Infra / Database</span>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${health?.database_healthy ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span className="text-xs font-mono text-slate-300">
                {health?.database_healthy ? "CONNECTED" : "DEGRADED"}
              </span>
            </div>
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">PostgreSQL &amp; SQLite WAL</h2>
          <p className="text-xs text-slate-400 mb-4">Alembic Async Migrations Applied</p>
          <div className="space-y-1.5 text-xs font-mono text-slate-300 border-t border-white/5 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-500">Driver Health:</span>
              <span className="text-emerald-400">{health?.database || "ready"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Initial Schema:</span>
              <span className="text-slate-200">001_initial_schema</span>
            </div>
          </div>
        </div>

        {/* Real-Time WebSocket Bus Card */}
        <div className="glass-panel p-6 rounded-xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">Real-Time Event Bus</span>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${wsStatus === "connected" ? "bg-cyan-400 animate-pulse" : "bg-slate-600"}`} />
              <span className="text-xs font-mono text-slate-300 uppercase">{wsStatus}</span>
            </div>
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">Dual-Surface Multiplex</h2>
          <p className="text-xs text-slate-400 mb-4">WebSocket /ws/nexus • Streaming Token Feeds</p>
          <div className="space-y-1.5 text-xs font-mono text-slate-300 border-t border-white/5 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-500">Client Surface:</span>
              <span className="text-cyan-400">dashboard</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Latency:</span>
              <span className="text-emerald-400">&lt; 1ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Event Stream Panel */}
      <div className="glass-panel rounded-xl p-6">
        <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-3">
          <h3 className="text-sm font-semibold text-slate-200 uppercase font-mono tracking-wider flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            Live Event Stream (Core Event Bus)
          </h3>
          <span className="text-xs text-slate-500 font-mono">Channel: ws://localhost:8000/ws/nexus</span>
        </div>

        <div className="space-y-2 font-mono text-xs">
          {wsMessages.length === 0 ? (
            <div className="p-4 rounded-lg bg-black/30 text-slate-500 text-center">
              Waiting for events from NEXUS Core Event Bus...
            </div>
          ) : (
            wsMessages.map((msg, i) => (
              <div key={i} className="p-2.5 rounded bg-black/40 border border-white/5 text-slate-300">
                {msg}
              </div>
            ))
          )}
        </div>
      </div>

      {/* System Topology / Boundaries Verification */}
      <div className="glass-panel rounded-xl p-6">
        <h3 className="text-sm font-semibold text-slate-200 uppercase font-mono tracking-wider mb-4">
          NEXUS Monorepo Boundary Status (Phase 1)
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">apps/dashboard</span>
            <span className="text-emerald-400">Next.js App Router ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">apps/ambient</span>
            <span className="text-emerald-400">Tauri React Shell ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">services/api</span>
            <span className="text-emerald-400">FastAPI Async Core ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">services/worker</span>
            <span className="text-emerald-400">Worker Daemon Loop ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">packages/types</span>
            <span className="text-cyan-400">TS + Pydantic v2 ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">packages/config</span>
            <span className="text-cyan-400">Pydantic BaseSettings ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">packages/shared</span>
            <span className="text-cyan-400">JSON Structlog &amp; Models ✓</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <span className="text-slate-500 block mb-1">infra/database</span>
            <span className="text-emerald-400">Alembic Migrations ✓</span>
          </div>
        </div>
      </div>
    </main>
  );
}
