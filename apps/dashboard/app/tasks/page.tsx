"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../src/context/AuthContext";
import { mockDAGs } from "../../src/mockData/mockTasks";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { TaskTimeline } from "../../src/components/ui/TaskTimeline";
import type { DAGNode, TaskDAG, TaskEvent, TaskStatus } from "@nexus/types";
import {
  Network,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  History,
  Radio,
  RefreshCw,
  AlertTriangle,
  Flame,
  ArrowRight,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export default function TasksPage() {
  const { token, isAuthenticated } = useAuth();

  const [dags, setDags] = useState<TaskDAG[]>(mockDAGs);
  const [selectedDAG, setSelectedDAG] = useState<TaskDAG>(mockDAGs[0]);
  const [selectedNode, setSelectedNode] = useState<DAGNode | undefined>(mockDAGs[0].nodes[0]);
  const [timelineEvents, setTimelineEvents] = useState<TaskEvent[]>([]);
  const [activeTab, setActiveTab] = useState<"dag" | "timeline">("dag");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal States
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>("User requested cancellation");

  // Create Task Form
  const [newGoal, setNewGoal] = useState<string>("");
  const [newSteps, setNewSteps] = useState<
    Array<{ name: string; agent: string; tool: string }>
  >([
    { name: "Decompose requirements", agent: "planner", tool: "" },
    { name: "Execute primary action", agent: "executor", tool: "terminal_runner" },
  ]);

  // Load Tasks from API
  const loadTasks = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const liveDags: TaskDAG[] = await res.json();
        if (liveDags.length > 0) {
          setDags(liveDags);
          // Preserve active selection if still present
          setSelectedDAG((prev) => {
            const found = liveDags.find((d) => d.dag_id === prev.dag_id);
            return found || liveDags[0];
          });
        }
      }
    } catch (err) {
      console.warn("Failed to fetch live tasks, displaying cached tasks:", err);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // Load Timeline Events for Selected DAG
  const loadTimeline = useCallback(
    async (dagId: string) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/api/v1/tasks/${dagId}/timeline`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setTimelineEvents(data.events || []);
        }
      } catch (err) {
        console.warn("Failed to fetch task timeline:", err);
      }
    },
    [token]
  );

  useEffect(() => {
    if (isAuthenticated && token) {
      loadTasks();
    }
  }, [isAuthenticated, token, loadTasks]);

  useEffect(() => {
    if (selectedDAG?.dag_id && token) {
      loadTimeline(selectedDAG.dag_id);
      if (selectedDAG.nodes?.length > 0) {
        setSelectedNode(selectedDAG.nodes[0]);
      } else {
        setSelectedNode(undefined);
      }
    }
  }, [selectedDAG?.dag_id, token, loadTimeline]);

  // WebSocket Live Updates Connection
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout | null = null;

    const connectWebSocket = () => {
      try {
        const wsUrl = `${WS_BASE}/ws/nexus?client_surface=dashboard&session_id=${
          selectedDAG?.session_id || "default"
        }`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const evtType = data.event_type;

            if (
              evtType === "dag.updated" ||
              evtType === "task.state_changed" ||
              evtType === "step.state_changed" ||
              evtType === "task.cancelled"
            ) {
              // Refresh task state dynamically
              loadTasks();
              if (selectedDAG?.dag_id) {
                loadTimeline(selectedDAG.dag_id);
              }
            }
          } catch {
            // Ignore non-JSON
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimer = setTimeout(connectWebSocket, 4000);
        };

        ws.onerror = () => {
          setWsConnected(false);
        };
      } catch {
        setWsConnected(false);
      }
    };

    connectWebSocket();

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [selectedDAG?.session_id, selectedDAG?.dag_id, loadTasks, loadTimeline]);

  // Handle Create Task
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoal.trim()) return;

    if (!token) {
      setErrorMessage("Please authenticate to submit persistent DAG tasks to NEXUS.");
      return;
    }

    try {
      const payload = {
        goal: newGoal,
        execution_metadata: { source: "dashboard_ui", created_surface: "web" },
        nodes: newSteps.map((s) => ({
          name: s.name,
          agent: s.agent,
          tool: s.tool || null,
        })),
      };

      const res = await fetch(`${API_BASE}/api/v1/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create task");
      }

      const created: TaskDAG = await res.json();
      setShowCreateModal(false);
      setNewGoal("");
      await loadTasks();
      setSelectedDAG(created);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Error creating task");
    }
  };

  // Handle Task Transition
  const handleTransitionTask = async (toState: TaskStatus) => {
    if (!token || !selectedDAG) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/tasks/${selectedDAG.dag_id}/transition`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          to_state: toState,
          reason: `Transitioned to ${toState} via dashboard console`,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Transition failed");
      }

      const updated = await res.json();
      setSelectedDAG(updated);
      await loadTasks();
      await loadTimeline(selectedDAG.dag_id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Transition failed");
    }
  };

  // Handle Step Transition
  const handleTransitionStep = async (stepId: string, toState: TaskStatus) => {
    if (!token || !selectedDAG) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/tasks/${selectedDAG.dag_id}/steps/${stepId}/transition`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ to_state: toState }),
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Step transition failed");
      }

      const updatedNode = await res.json();
      setSelectedNode(updatedNode);
      await loadTasks();
      await loadTimeline(selectedDAG.dag_id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Step transition failed");
    }
  };

  // Handle Task Cancellation
  const handleCancelTask = async () => {
    if (!token || !selectedDAG) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/tasks/${selectedDAG.dag_id}/cancel`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ reason: cancelReason }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Cancellation failed");
      }

      const updated = await res.json();
      setSelectedDAG(updated);
      setShowCancelModal(false);
      await loadTasks();
      await loadTimeline(selectedDAG.dag_id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Cancellation failed");
    }
  };

  const isTerminal =
    selectedDAG.status === "completed" ||
    selectedDAG.status === "failed" ||
    selectedDAG.status === "cancelled";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-4 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">Tasks &amp; Topological DAGs</h2>
            <div
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono border ${
                wsConnected
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}
            >
              <Radio size={10} className={wsConnected ? "animate-pulse" : ""} />
              {wsConnected ? "LIVE WS" : "OFFLINE"}
            </div>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Deterministic Directed Acyclic Graphs synthesized by the NEXUS Task Engine
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadTasks}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-900 border border-white/10 text-slate-400 hover:text-white transition-all"
            title="Refresh Tasks"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          </button>

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-mono text-xs font-semibold shadow-lg shadow-cyan-500/20 hover:brightness-110 transition-all"
          >
            <Plus size={14} />
            <span>New Task DAG</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="flex items-center justify-between p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 font-mono text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-400 hover:text-white font-bold ml-4"
          >
            &times;
          </button>
        </div>
      )}

      {/* Task DAG Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-white/5 scrollbar-none">
        {dags.map((dag) => (
          <button
            key={dag.dag_id}
            onClick={() => {
              setSelectedDAG(dag);
              setSelectedNode(dag.nodes[0]);
            }}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-xs transition-all border whitespace-nowrap shrink-0 ${
              selectedDAG.dag_id === dag.dag_id
                ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400 shadow-md shadow-cyan-500/10"
                : "bg-slate-900/80 border-white/10 text-slate-400 hover:text-white"
            }`}
          >
            <Network size={12} />
            <span>{dag.dag_id.slice(0, 14)}</span>
            <span
              className={`w-2 h-2 rounded-full ${
                dag.status === "completed"
                  ? "bg-emerald-400"
                  : dag.status === "executing"
                  ? "bg-cyan-400 animate-pulse"
                  : dag.status === "cancelled"
                  ? "bg-slate-500"
                  : "bg-amber-400"
              }`}
            />
          </button>
        ))}
      </div>

      {/* Main Grid: Left Timeline / Right Inspector & Audit */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: DAG Plan & Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <Card
            title={
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Network size={16} className="text-cyan-400" />
                  <span>DAG: {selectedDAG.dag_id}</span>
                </div>
                {/* View Switcher: DAG vs Timeline */}
                <div className="flex items-center rounded-lg bg-black/40 border border-white/10 p-0.5 text-[11px] font-mono">
                  <button
                    onClick={() => setActiveTab("dag")}
                    className={`px-2.5 py-1 rounded-md transition-colors ${
                      activeTab === "dag" ? "bg-cyan-500/20 text-cyan-300 font-semibold" : "text-slate-400"
                    }`}
                  >
                    Subtasks ({selectedDAG.nodes?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveTab("timeline")}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                      activeTab === "timeline" ? "bg-cyan-500/20 text-cyan-300 font-semibold" : "text-slate-400"
                    }`}
                  >
                    <History size={12} />
                    <span>Timeline ({timelineEvents.length})</span>
                  </button>
                </div>
              </div>
            }
            subtitle={selectedDAG.goal}
            badge={<StatusBadge status={selectedDAG.status} />}
          >
            {/* Action Bar for Task Lifecycle Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 my-4 rounded-xl bg-slate-950/60 border border-white/5 font-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-500">Lifecycle Engine:</span>
                <span className="text-slate-200 font-bold uppercase tracking-wider">
                  {selectedDAG.status}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Step Transitions */}
                {!isTerminal && (
                  <>
                    {selectedDAG.status === "pending" && (
                      <button
                        onClick={() => handleTransitionTask("planning")}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-300 hover:bg-amber-500/30 transition-all text-[11px]"
                      >
                        <Play size={12} />
                        <span>Start Planning</span>
                      </button>
                    )}
                    {(selectedDAG.status === "planning" ||
                      selectedDAG.status === "awaiting_approval" ||
                      selectedDAG.status === "observing") && (
                      <button
                        onClick={() => handleTransitionTask("executing")}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/30 transition-all text-[11px]"
                      >
                        <Play size={12} />
                        <span>Execute DAG</span>
                      </button>
                    )}
                    {selectedDAG.status === "executing" && (
                      <>
                        <button
                          onClick={() => handleTransitionTask("observing")}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-300 hover:bg-purple-500/30 transition-all text-[11px]"
                        >
                          <span>Observe Output</span>
                        </button>
                        <button
                          onClick={() => handleTransitionTask("completed")}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-all text-[11px]"
                        >
                          <CheckCircle2 size={12} />
                          <span>Mark Complete</span>
                        </button>
                      </>
                    )}
                    {selectedDAG.status === "observing" && (
                      <button
                        onClick={() => handleTransitionTask("completed")}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-all text-[11px]"
                      >
                        <CheckCircle2 size={12} />
                        <span>Finish Task</span>
                      </button>
                    )}

                    <button
                      onClick={() => setShowCancelModal(true)}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 transition-all text-[11px]"
                    >
                      <XCircle size={12} />
                      <span>Cancel Task</span>
                    </button>
                  </>
                )}

                {isTerminal && (
                  <span className="text-[11px] text-slate-500 italic">
                    Task is in irreversible terminal state
                  </span>
                )}
              </div>
            </div>

            {/* Tab 1: DAG Nodes Timeline */}
            {activeTab === "dag" ? (
              <div className="mt-4">
                <TaskTimeline
                  nodes={selectedDAG.nodes}
                  activeNodeId={selectedNode?.id}
                  onSelectNode={(node) => setSelectedNode(node)}
                />
              </div>
            ) : (
              /* Tab 2: Chronological Event Audit Timeline */
              <div className="mt-4 space-y-3 font-mono">
                {timelineEvents.length === 0 ? (
                  <div className="text-center p-8 text-xs text-slate-500">
                    No timeline events recorded yet.
                  </div>
                ) : (
                  timelineEvents.map((evt, idx) => (
                    <div
                      key={evt.id || idx}
                      className="p-3 rounded-xl bg-slate-900/60 border border-white/5 space-y-1 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-cyan-400">{evt.event_type}</span>
                        <span className="text-[10px] text-slate-500">
                          {new Date(evt.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-slate-300 text-[11px]">{evt.message}</p>
                      {evt.from_state && evt.to_state && (
                        <div className="flex items-center gap-2 text-[10px] text-slate-400">
                          <span>{evt.from_state}</span>
                          <ArrowRight size={10} />
                          <span className="text-emerald-400 font-semibold">{evt.to_state}</span>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Node Step Inspector */}
        <div>
          <Card
            title={selectedNode ? selectedNode.name : "Step Inspector"}
            subtitle={selectedNode ? `Node ID: ${selectedNode.id}` : "Select a step to inspect"}
            badge={selectedNode && <StatusBadge status={selectedNode.status} />}
          >
            {selectedNode ? (
              <div className="space-y-4 font-mono text-xs">
                {/* Inspector Controls */}
                {!isTerminal && selectedNode.status !== "completed" && (
                  <div className="p-3 rounded-xl bg-slate-900/80 border border-white/10 space-y-2">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-bold">
                      Subtask Execution Controls
                    </span>
                    <div className="flex gap-2">
                      {selectedNode.status !== "executing" && (
                        <button
                          onClick={() => handleTransitionStep(selectedNode.id, "executing")}
                          className="flex-1 py-1 px-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 text-[11px] hover:bg-cyan-500/30"
                        >
                          Start Step
                        </button>
                      )}
                      <button
                        onClick={() => handleTransitionStep(selectedNode.id, "completed")}
                        className="flex-1 py-1 px-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-[11px] hover:bg-emerald-500/30"
                      >
                        Complete Step
                      </button>
                    </div>
                  </div>
                )}

                <div className="space-y-2 border-b border-white/10 pb-3">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Agent:</span>
                    <span className="text-slate-200 font-bold">{selectedNode.agent}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Designated Tool:</span>
                    <span className="text-cyan-400">{selectedNode.tool || "None"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Dependencies:</span>
                    <span className="text-slate-300">
                      {selectedNode.dependencies.length > 0
                        ? selectedNode.dependencies.join(", ")
                        : "None (Root node)"}
                    </span>
                  </div>
                  {selectedNode.started_at && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Started At:</span>
                      <span className="text-slate-400">
                        {new Date(selectedNode.started_at).toLocaleTimeString()}
                      </span>
                    </div>
                  )}
                  {selectedNode.completed_at && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Completed At:</span>
                      <span className="text-emerald-400">
                        {new Date(selectedNode.completed_at).toLocaleTimeString()}
                      </span>
                    </div>
                  )}
                </div>

                {/* Input Parameters */}
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1">
                    Input Parameters
                  </span>
                  <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                    {JSON.stringify(selectedNode.input || {}, null, 2)}
                  </pre>
                </div>

                {/* Result / Observation */}
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1">
                    Result / Observation
                  </span>
                  <pre className="p-3 rounded-lg bg-black/60 border border-white/5 text-slate-300 overflow-x-auto text-[11px]">
                    {JSON.stringify(
                      selectedNode.result || { status: selectedNode.status },
                      null,
                      2
                    )}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-center p-6 text-xs text-slate-500 font-mono">
                Click any step in the timeline to inspect metadata, inputs, and results.
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Modal: Create Task DAG */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 font-mono">
          <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Flame size={16} className="text-cyan-400" />
                <span>Synthesize Task DAG</span>
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-500 hover:text-white"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Objective / Goal</label>
                <textarea
                  value={newGoal}
                  onChange={(e) => setNewGoal(e.target.value)}
                  placeholder="e.g. Audit micro-benchmarks and compile system latency profile"
                  className="w-full p-2.5 rounded-lg bg-black/50 border border-white/10 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 resize-none h-20"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Decomposed Subtasks (Steps)</label>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {newSteps.map((step, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-black/40 border border-white/5 space-y-2"
                    >
                      <input
                        type="text"
                        placeholder="Step title"
                        value={step.name}
                        onChange={(e) => {
                          const updated = [...newSteps];
                          updated[idx].name = e.target.value;
                          setNewSteps(updated);
                        }}
                        className="w-full p-1.5 rounded bg-slate-900 border border-white/10 text-white text-[11px]"
                        required
                      />
                      <div className="flex gap-2">
                        <select
                          value={step.agent}
                          onChange={(e) => {
                            const updated = [...newSteps];
                            updated[idx].agent = e.target.value;
                            setNewSteps(updated);
                          }}
                          className="flex-1 p-1 rounded bg-slate-900 border border-white/10 text-slate-300 text-[10px]"
                        >
                          <option value="planner">planner</option>
                          <option value="executor">executor</option>
                          <option value="orchestrator">orchestrator</option>
                          <option value="observer">observer</option>
                        </select>
                        <input
                          type="text"
                          placeholder="Tool (optional)"
                          value={step.tool}
                          onChange={(e) => {
                            const updated = [...newSteps];
                            updated[idx].tool = e.target.value;
                            setNewSteps(updated);
                          }}
                          className="flex-1 p-1 rounded bg-slate-900 border border-white/10 text-white text-[10px]"
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setNewSteps([
                      ...newSteps,
                      { name: `Subtask ${newSteps.length + 1}`, agent: "executor", tool: "" },
                    ])
                  }
                  className="mt-2 text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                >
                  <Plus size={12} /> Add Step
                </button>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold shadow-md shadow-cyan-500/20"
                >
                  Create DAG
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Cancel Task Confirmation */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 font-mono">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-rose-500/30 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertTriangle size={20} />
              <h3 className="text-base font-bold text-white">Cancel Task DAG</h3>
            </div>
            <p className="text-xs text-slate-400">
              Are you sure you want to cancel{" "}
              <strong className="text-slate-200">{selectedDAG.dag_id}</strong>? Cascading
              cancellation will terminate all ongoing and pending subtasks immediately.
            </p>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Cancellation Reason</label>
              <input
                type="text"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full p-2 rounded-lg bg-black/50 border border-white/10 text-white text-xs"
              />
            </div>
            <div className="flex justify-end gap-3 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={() => setShowCancelModal(false)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs"
              >
                Go Back
              </button>
              <button
                type="button"
                onClick={handleCancelTask}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow-md shadow-rose-600/20"
              >
                Confirm Cancellation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
