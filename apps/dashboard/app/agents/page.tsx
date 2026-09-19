"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../src/context/AuthContext";
import { mockAgents } from "../../src/mockData/mockAgents";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { AgentMessage, AgentRosterItem, ExecutionPlan } from "@nexus/types";
import {
  Bot,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  RefreshCw,
  Send,
  MessageSquare,
  FileText,
  Search,
  Check,
  AlertTriangle,
  StopCircle,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AgentsPage() {
  const { token, isAuthenticated } = useAuth();

  const [roster, setRoster] = useState<AgentRosterItem[]>([]);
  const [isLoadingRoster, setIsLoadingRoster] = useState<boolean>(false);

  // Autonomous Execution Studio state
  const [goal, setGoal] = useState<string>("Research recent papers on autonomous multi-agent planning and summarize findings");
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [activePlan, setActivePlan] = useState<ExecutionPlan | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [finalResponse, setFinalResponse] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load Agent Roster
  const loadRoster = useCallback(async () => {
    if (!token) return;
    setIsLoadingRoster(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/agents/roster`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRoster(data);
      }
    } catch (err) {
      console.warn("Failed to fetch live agent roster, fallback to local:", err);
    } finally {
      setIsLoadingRoster(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated && token) {
      loadRoster();
    }
  }, [isAuthenticated, token, loadRoster]);

  // Execute Goal through Orchestrator
  const handleExecuteGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goal.trim() || !token) return;

    setIsExecuting(true);
    setErrorMessage(null);
    setFinalResponse(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/agents/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          goal,
          auto_run: true,
          context: { source: "dashboard_studio" },
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Agent execution failed");
      }

      const data = await res.json();
      setActivePlan(data.plan);
      setMessages(data.messages || []);
      setFinalResponse(data.final_response || null);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setIsExecuting(false);
    }
  };

  // Replan Trigger
  const handleTriggerReplan = async () => {
    if (!activePlan || !token) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/agents/plans/${activePlan.id}/replan`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ reason: "User requested manual replanning" }),
      });
      if (res.ok) {
        const updated = await res.json();
        setActivePlan(updated);
      }
    } catch (err) {
      console.warn("Replan failed:", err);
    }
  };

  // Agent Icon Helper
  const getAgentIcon = (agentType: string) => {
    switch (agentType.toLowerCase()) {
      case "research":
        return <Search size={14} className="text-purple-400" />;
      case "document":
        return <FileText size={14} className="text-amber-400" />;
      case "planning":
        return <Sparkles size={14} className="text-emerald-400" />;
      default:
        return <Bot size={14} className="text-cyan-400" />;
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-4 gap-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white flex items-center gap-2">
            <Sparkles size={20} className="text-cyan-400" />
            <span>Autonomous Multi-Agent Orchestrator</span>
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Phase 8: Role-bounded specialized agents coordinating via structured Pydantic contracts &amp; verified execution plans
          </p>
        </div>
        <button
          onClick={loadRoster}
          disabled={isLoadingRoster}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono text-slate-300 hover:text-white hover:bg-slate-800 transition-all self-start sm:self-auto"
        >
          <RefreshCw size={12} className={isLoadingRoster ? "animate-spin" : ""} />
          <span>Refresh Roster</span>
        </button>
      </div>

      {/* Autonomous Goal Execution Studio */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Play size={16} className="text-emerald-400" />
            <span className="font-mono text-sm font-bold">Autonomous Execution Studio</span>
          </div>
        }
        subtitle="Submit a high-level goal. The Orchestrator will synthesize a dependency DAG, route subtasks to specialists, and synthesize verified results."
      >
        <form onSubmit={handleExecuteGoal} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-slate-400 uppercase mb-1.5">
              High-Level Objective / Goal
            </label>
            <textarea
              rows={2}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g., Investigate system memory leak, review indexed technical documentation, and summarize root causes"
              className="w-full px-3 py-2 rounded-xl bg-slate-950/80 border border-white/10 text-sm font-mono text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-all"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="text-xs font-mono text-slate-500">
              Active Agents: <span className="text-cyan-400">Orchestrator</span> &bull; <span className="text-emerald-400">Planning</span> &bull; <span className="text-purple-400">Research</span> &bull; <span className="text-amber-400">Document</span>
            </div>
            <button
              type="submit"
              disabled={isExecuting || !goal.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold transition-all disabled:opacity-50 shadow-lg shadow-cyan-600/20"
            >
              {isExecuting ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Orchestrating...</span>
                </>
              ) : (
                <>
                  <Send size={14} />
                  <span>Dispatch Autonomous Plan</span>
                </>
              )}
            </button>
          </div>
        </form>

        {errorMessage && (
          <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono flex items-center gap-2">
            <AlertTriangle size={14} />
            <span>{errorMessage}</span>
          </div>
        )}
      </Card>

      {/* Live Execution Plan & Agent Feed */}
      {activePlan && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Plan Steps Checklist */}
          <Card
            title={
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-cyan-400" />
                  <span className="font-mono text-sm">Execution Plan: {activePlan.id.slice(0, 16)}</span>
                </div>
                <StatusBadge status={activePlan.status} />
              </div>
            }
            subtitle={activePlan.goal}
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-b border-white/5 pb-2">
                <span>Progress: {activePlan.steps.filter((s) => s.status === "completed").length} / {activePlan.steps.length} Steps</span>
                <span>Replans: {activePlan.replan_count} / {activePlan.max_replans}</span>
              </div>

              <div className="space-y-2.5">
                {activePlan.steps.map((step, idx) => (
                  <div
                    key={step.id || idx}
                    className={`p-3 rounded-xl border transition-all ${
                      step.status === "completed"
                        ? "bg-emerald-950/20 border-emerald-500/30"
                        : step.status === "in_progress"
                        ? "bg-cyan-950/30 border-cyan-500/50 shadow-md shadow-cyan-500/10"
                        : step.status === "failed"
                        ? "bg-rose-950/20 border-rose-500/30"
                        : step.status === "skipped"
                        ? "bg-slate-900/40 border-slate-700/30 opacity-60"
                        : "bg-slate-950/60 border-white/5"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2.5">
                        <div className="mt-0.5">{getAgentIcon(step.assigned_agent || "orchestrator")}</div>
                        <div>
                          <div className="text-xs font-mono text-white font-medium">
                            {step.description || step.name}
                          </div>
                          <div className="flex items-center gap-2 mt-1 text-[11px] font-mono text-slate-400">
                            <span className="text-cyan-400 font-semibold uppercase">{step.assigned_agent}</span>
                            {step.dependencies && step.dependencies.length > 0 && (
                              <span>&bull; Depends on: {step.dependencies.join(", ")}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <StatusBadge status={step.status || "pending"} />
                    </div>

                    {Boolean(step.result) && (
                      <div className="mt-2.5 p-2 rounded bg-black/50 border border-white/5 text-[11px] font-mono text-slate-300">
                        <span className="text-slate-500 block text-[10px] uppercase">Step Result:</span>
                        <pre className="text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-24">
                          {typeof step.result === "object" ? JSON.stringify(step.result, null, 2) : String(step.result)}
                        </pre>
                      </div>
                    )}

                    {step.error && (
                      <div className="mt-2 p-2 rounded bg-rose-950/30 border border-rose-500/20 text-rose-300 text-[11px] font-mono">
                        Error: {step.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {activePlan.status === "failed" && activePlan.replan_count < activePlan.max_replans && (
                <button
                  onClick={handleTriggerReplan}
                  className="w-full py-2 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-300 hover:bg-purple-600/30 text-xs font-mono font-semibold transition-all"
                >
                  Trigger Recovery Replan
                </button>
              )}
            </div>
          </Card>

          {/* Agent Communication & Verified Result */}
          <div className="space-y-6">
            {finalResponse && (
              <Card
                title={
                  <div className="flex items-center gap-2">
                    <Check size={16} className="text-emerald-400" />
                    <span className="font-mono text-sm text-emerald-300 font-bold">Verified Final Synthesis</span>
                  </div>
                }
              >
                <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20 text-xs font-mono text-slate-200 leading-relaxed">
                  {finalResponse}
                </div>
              </Card>
            )}

            <Card
              title={
                <div className="flex items-center gap-2">
                  <MessageSquare size={16} className="text-purple-400" />
                  <span className="font-mono text-sm">Agent Communication Bus</span>
                </div>
              }
              subtitle="Structured messages and lifecycle state transitions"
            >
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {messages.length === 0 ? (
                  <div className="text-center py-8 text-xs font-mono text-slate-500">
                    No communication messages captured yet.
                  </div>
                ) : (
                  messages.map((msg, idx) => (
                    <div
                      key={msg.id || idx}
                      className="p-3 rounded-xl bg-slate-950/70 border border-white/5 font-mono text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-[10px] text-slate-500">
                        <div className="flex items-center gap-1.5">
                          {getAgentIcon(msg.sender)}
                          <span className="font-bold uppercase text-slate-300">{msg.sender}</span>
                          <span>&rarr;</span>
                          <span className="text-slate-400 uppercase">{msg.recipient}</span>
                        </div>
                        <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed">{msg.content}</p>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Grid of Agent Cards from Roster */}
      <div>
        <h3 className="text-sm font-bold font-mono text-white uppercase tracking-wider mb-4">
          Active Specialized Agents
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {(roster.length > 0 ? roster : mockAgents.map(a => ({
            agent_type: a.id,
            name: a.name,
            description: a.description,
            allowed_tools: a.allowed_tools,
            assigned_model: a.assigned_model,
            status: a.status,
            system_prompt_preview: a.system_prompt_preview,
          }))).map((agent) => (
            <Card
              key={agent.agent_type}
              title={
                <div className="flex items-center gap-2">
                  {getAgentIcon(agent.agent_type)}
                  <span className="font-mono text-sm">{agent.name}</span>
                </div>
              }
              badge={<StatusBadge status={agent.status} />}
              subtitle={agent.agent_type.toUpperCase()}
            >
              <div className="space-y-4 font-mono text-xs">
                <p className="text-slate-300 leading-relaxed text-[12px]">
                  {agent.description}
                </p>

                <div className="grid grid-cols-2 gap-3 border-t border-white/5 pt-3">
                  <div className="p-2.5 rounded bg-slate-900 border border-white/5">
                    <span className="text-slate-500 text-[10px] uppercase block">Assigned Model</span>
                    <span className="text-cyan-300 font-semibold">{agent.assigned_model}</span>
                  </div>
                  <div className="p-2.5 rounded bg-slate-900 border border-white/5">
                    <span className="text-slate-500 text-[10px] uppercase block">Granted Tools</span>
                    <span className="text-emerald-400 font-semibold">
                      {agent.allowed_tools.length} Tools
                    </span>
                  </div>
                </div>

                {/* Tools Badges */}
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block mb-1.5">
                    Authorized Capabilities
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {agent.allowed_tools.map((t) => (
                      <span
                        key={t}
                        className="px-2 py-0.5 rounded bg-slate-950 border border-white/10 text-[11px] text-slate-300"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
