"use client";

import React, { useState } from "react";
import { mockSessions, type SessionItem } from "../../src/mockData/mockSessions";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { MessageSquareCode, Monitor, Terminal, Clock, Folder } from "lucide-react";

export default function SessionsPage() {
  const [selectedSession, setSelectedSession] = useState<SessionItem>(mockSessions[0]);
  const [filterSurface, setFilterSurface] = useState<"all" | "dashboard" | "ambient">("all");

  const filtered = mockSessions.filter(
    (s) => filterSurface === "all" || s.surface === filterSurface
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">AI Sessions &amp; Context</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Multi-turn conversation sessions multiplexed across Dashboard and Ambient HUD
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2 p-1 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono">
          {(["all", "dashboard", "ambient"] as const).map((surface) => (
            <button
              key={surface}
              onClick={() => setFilterSurface(surface)}
              className={`px-3 py-1 rounded-md transition-colors uppercase ${
                filterSurface === surface
                  ? "bg-cyan-500 text-slate-950 font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {surface}
            </button>
          ))}
        </div>
      </div>

      {/* Two-Column Layout: Session List & Session Detail */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Session List */}
        <div className="space-y-3">
          {filtered.map((s) => {
            const isSelected = s.id === selectedSession.id;
            return (
              <div
                key={s.id}
                onClick={() => setSelectedSession(s)}
                className={`p-4 rounded-xl border transition-all cursor-pointer font-mono ${
                  isSelected
                    ? "glass-panel border-cyan-500/50 shadow-lg shadow-cyan-500/10"
                    : "bg-slate-950/60 border-white/5 hover:border-white/20"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-slate-500 uppercase">{s.id}</span>
                  <StatusBadge
                    label={s.surface.toUpperCase()}
                    status={s.surface === "ambient" ? "planning" : "ready"}
                  />
                </div>
                <h3 className="text-xs font-bold text-slate-200 line-clamp-2 mb-2">
                  {s.title}
                </h3>
                <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-white/5 pt-2">
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {s.created_at.split(" ")[1]}
                  </span>
                  <span>{s.message_count} messages</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Selected Session Detail & Inspector */}
        <div className="md:col-span-2 space-y-6">
          <Card
            title={selectedSession.title}
            badge={<StatusBadge label={selectedSession.surface.toUpperCase()} />}
            subtitle={`Session ID: ${selectedSession.id} • Started: ${selectedSession.created_at}`}
          >
            {/* OS Context Captured at Session Inception */}
            <div className="mb-6 p-4 rounded-xl bg-slate-950 border border-white/10 font-mono text-xs space-y-2">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold block mb-2">
                Captured Host OS Context (MacOSAdapter):
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="flex items-center gap-2 text-slate-300">
                  <Monitor size={14} className="text-cyan-400 shrink-0" />
                  <span className="truncate">App: <strong>{selectedSession.os_context.active_app}</strong></span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <Terminal size={14} className="text-cyan-400 shrink-0" />
                  <span className="truncate">Window: {selectedSession.os_context.window_title}</span>
                </div>
                <div className="sm:col-span-2 flex items-center gap-2 text-slate-400 text-[11px]">
                  <Folder size={14} className="text-slate-500 shrink-0" />
                  <span className="truncate">Cwd: <code>{selectedSession.os_context.cwd}</code></span>
                </div>
              </div>
            </div>

            {/* Simulated Multi-Turn Transcript */}
            <div className="space-y-4 font-mono text-xs">
              {/* User Turn */}
              <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-slate-200">
                <div className="flex items-center justify-between text-cyan-400 text-[11px] mb-1 font-bold">
                  <span>USER REQUEST</span>
                  <span>{selectedSession.created_at}</span>
                </div>
                <p>{selectedSession.title}</p>
              </div>

              {/* Orchestrator Reasoning */}
              <div className="p-3.5 rounded-xl bg-slate-900 border border-white/5 text-slate-300 space-y-2">
                <div className="flex items-center justify-between text-sky-400 text-[11px] font-bold">
                  <span>ORCHESTRATOR AGENT (DAG PLANNING)</span>
                  <span>claude-3-5-sonnet</span>
                </div>
                <p className="text-slate-400">
                  Analyzing repository structure. Detected existing FastAPI middleware in{" "}
                  <code>services/api/nexus_api/middleware.py</code>. Synthesizing 4-step execution DAG with diff-based approval requirement.
                </p>
              </div>

              {/* Tool Execution Observation */}
              <div className="p-3.5 rounded-xl bg-black/40 border border-white/10 text-slate-300">
                <div className="flex items-center justify-between text-emerald-400 text-[11px] mb-1 font-bold">
                  <span>TOOL OBSERVATION: filesystem.read</span>
                  <span>exit: 0</span>
                </div>
                <pre className="text-[11px] text-slate-400 overflow-x-auto p-2 bg-black/60 rounded">
{`class LoggingAndTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)`}
                </pre>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
