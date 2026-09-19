"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../src/context/AuthContext";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { Goal, GoalMilestone, GoalStatus } from "@nexus/types";
import {
  Target,
  CheckCircle2,
  Plus,
  RefreshCw,
  AlertTriangle,
  Flame,
  Pause,
  Play,
  Trash2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const fallbackGoals: Goal[] = [
  {
    id: "goal_01",
    user_id: "usr_mock",
    title: "Implement Production-Grade Security & Policy Kernel",
    description: "Multi-tier risk matrix, diff inspection, and reversibility",
    category: "Architecture",
    progress: 75,
    status: "active",
    milestones: [
      { id: "m1", title: "Define 4-tier risk matrix (LOW, MEDIUM, HIGH, CRITICAL)", completed: true },
      { id: "m2", title: "Pre-execution file snapshot & SHA-256 diff engine", completed: true },
      { id: "m3", title: "Diff-based interactive approval modal", completed: true },
      { id: "m4", title: "Automated rollback / undo handler integration", completed: false },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "goal_02",
    user_id: "usr_mock",
    title: "Dual Surface Ambient Overlay & Global Hotkey Protocol",
    description: "HUD shell with simulated hotkey listener",
    category: "Client Surfaces",
    progress: 100,
    status: "completed",
    milestones: [
      { id: "m5", title: "Tauri-ready React desktop HUD shell", completed: true },
      { id: "m6", title: "Simulated global hotkey listener (Cmd+Shift+Space)", completed: true },
      { id: "m7", title: "WebSocket real-time event multiplexing with Dashboard", completed: true },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export default function GoalsPage() {
  const { token, isAuthenticated } = useAuth();

  const [goals, setGoals] = useState<Goal[]>(fallbackGoals);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>("");
  const [newDescription, setNewDescription] = useState<string>("");
  const [newCategory, setNewCategory] = useState<string>("Engineering");
  const [newMilestones, setNewMilestones] = useState<string[]>([
    "Synthesize task decomposition",
    "Implement core test suite",
  ]);

  const loadGoals = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/goals`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const liveGoals: Goal[] = await res.json();
        if (liveGoals.length > 0) {
          setGoals(liveGoals);
        }
      }
    } catch (err) {
      console.warn("Failed to fetch live goals, using fallback:", err);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated && token) {
      loadGoals();
    }
  }, [isAuthenticated, token, loadGoals]);

  // Handle Create Goal
  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    if (!token) {
      setErrorMessage("Please authenticate to persist goals to NEXUS.");
      return;
    }

    try {
      const milestonesPayload: GoalMilestone[] = newMilestones
        .filter((m) => m.trim().length > 0)
        .map((m, idx) => ({
          id: `ms_${idx + 1}`,
          title: m,
          completed: false,
        }));

      const res = await fetch(`${API_BASE}/api/v1/goals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: newTitle,
          description: newDescription,
          category: newCategory,
          milestones: milestonesPayload,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create goal");
      }

      setShowCreateModal(false);
      setNewTitle("");
      setNewDescription("");
      await loadGoals();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Error creating goal");
    }
  };

  // Toggle milestone completed state
  const handleToggleMilestone = async (goal: Goal, milestoneId: string) => {
    const updatedMilestones = goal.milestones.map((m) =>
      m.id === milestoneId ? { ...m, completed: !m.completed } : m
    );

    if (!token) {
      // Offline local optimistic update
      const completedCount = updatedMilestones.filter((m) => m.completed).length;
      const progress = Math.round((completedCount / updatedMilestones.length) * 100);
      setGoals((prev) =>
        prev.map((g) =>
          g.id === goal.id
            ? {
                ...g,
                milestones: updatedMilestones,
                progress,
                status: progress === 100 ? "completed" : g.status,
              }
            : g
        )
      );
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/goals/${goal.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ milestones: updatedMilestones }),
      });

      if (res.ok) {
        const updatedGoal = await res.json();
        setGoals((prev) => prev.map((g) => (g.id === goal.id ? updatedGoal : g)));
      }
    } catch (err) {
      console.error("Failed to update milestone:", err);
    }
  };

  // Toggle goal pause/active status
  const handleToggleStatus = async (goal: Goal) => {
    const nextStatus: GoalStatus = goal.status === "active" ? "paused" : "active";
    if (!token) {
      setGoals((prev) =>
        prev.map((g) => (g.id === goal.id ? { ...g, status: nextStatus } : g))
      );
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/goals/${goal.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (res.ok) {
        const updated = await res.json();
        setGoals((prev) => prev.map((g) => (g.id === goal.id ? updated : g)));
      }
    } catch (err) {
      console.error("Failed to update goal status:", err);
    }
  };

  // Delete goal
  const handleDeleteGoal = async (goalId: string) => {
    if (!token) {
      setGoals((prev) => prev.filter((g) => g.id !== goalId));
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/goals/${goalId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setGoals((prev) => prev.filter((g) => g.id !== goalId));
      }
    } catch (err) {
      console.error("Failed to delete goal:", err);
    }
  };

  const filteredGoals = goals.filter((g) => {
    if (filterStatus === "all") return true;
    return g.status === filterStatus;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-4 gap-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Autonomous Goals</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            High-level mission objectives decomposed into milestone DAGs
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadGoals}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-900 border border-white/10 text-slate-400 hover:text-white transition-all"
            title="Refresh Goals"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          </button>

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-mono text-xs font-semibold shadow-lg shadow-cyan-500/20 hover:brightness-110 transition-all"
          >
            <Plus size={14} />
            <span>New Goal</span>
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

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 font-mono text-xs">
        {["all", "active", "paused", "completed"].map((st) => (
          <button
            key={st}
            onClick={() => setFilterStatus(st)}
            className={`px-3 py-1 rounded-lg capitalize border transition-all ${
              filterStatus === st
                ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-300 font-bold"
                : "bg-slate-900/60 border-white/5 text-slate-400 hover:text-white"
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Goals Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredGoals.map((goal) => (
          <Card
            key={goal.id}
            title={
              <div className="flex items-center gap-2">
                <Target size={16} className="text-cyan-400 shrink-0" />
                <span className="truncate">{goal.title}</span>
              </div>
            }
            badge={<StatusBadge status={goal.status} />}
            subtitle={`Category: ${goal.category}`}
          >
            {goal.description && (
              <p className="text-xs text-slate-400 font-mono line-clamp-2 my-2">
                {goal.description}
              </p>
            )}

            {/* Progress Bar */}
            <div className="my-3 space-y-1 font-mono text-xs">
              <div className="flex justify-between text-slate-400 text-[11px]">
                <span>Progress</span>
                <span className="text-white font-bold">{goal.progress}%</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    goal.status === "completed"
                      ? "bg-emerald-400"
                      : "bg-gradient-to-r from-cyan-400 to-blue-500"
                  }`}
                  style={{ width: `${goal.progress}%` }}
                />
              </div>
            </div>

            {/* Milestones List */}
            <div className="mt-4 space-y-2 border-t border-white/5 pt-3 font-mono text-xs">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                Decomposed Milestones ({goal.milestones.length})
              </span>
              {goal.milestones.map((m) => (
                <div
                  key={m.id}
                  onClick={() => handleToggleMilestone(goal, m.id)}
                  className="flex items-start gap-2 text-slate-300 cursor-pointer hover:text-white transition-colors group"
                >
                  <CheckCircle2
                    size={14}
                    className={`shrink-0 mt-0.5 transition-colors ${
                      m.completed
                        ? "text-emerald-400"
                        : "text-slate-600 group-hover:text-slate-400"
                    }`}
                  />
                  <span className={m.completed ? "line-through text-slate-500 text-[11px]" : "text-[11px]"}>
                    {m.title}
                  </span>
                </div>
              ))}
            </div>

            {/* Card Actions */}
            <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between font-mono text-[11px]">
              <button
                onClick={() => handleToggleStatus(goal)}
                className="flex items-center gap-1 text-slate-400 hover:text-cyan-300 transition-colors"
              >
                {goal.status === "active" ? (
                  <>
                    <Pause size={12} /> Pause
                  </>
                ) : (
                  <>
                    <Play size={12} /> Activate
                  </>
                )}
              </button>

              <button
                onClick={() => handleDeleteGoal(goal.id)}
                className="flex items-center gap-1 text-slate-500 hover:text-rose-400 transition-colors"
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          </Card>
        ))}
      </div>

      {/* Modal: Create Goal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 font-mono">
          <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Flame size={16} className="text-cyan-400" />
                <span>Define Autonomous Goal</span>
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-500 hover:text-white"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateGoal} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Goal Title</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Build end-to-end memory recall pipeline"
                  className="w-full p-2.5 rounded-lg bg-black/50 border border-white/10 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 text-xs"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Description (Optional)</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Detailed architectural scope or success criteria"
                  className="w-full p-2.5 rounded-lg bg-black/50 border border-white/10 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 resize-none h-16 text-xs"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Category</label>
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  className="w-full p-2 rounded-lg bg-slate-800 border border-white/10 text-slate-300 text-xs"
                >
                  <option value="Architecture">Architecture</option>
                  <option value="Intelligence">Intelligence</option>
                  <option value="Client Surfaces">Client Surfaces</option>
                  <option value="Security">Security</option>
                  <option value="Infrastructure">Infrastructure</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Milestones</label>
                <div className="space-y-2">
                  {newMilestones.map((ms, idx) => (
                    <div key={idx} className="flex gap-2">
                      <input
                        type="text"
                        value={ms}
                        onChange={(e) => {
                          const updated = [...newMilestones];
                          updated[idx] = e.target.value;
                          setNewMilestones(updated);
                        }}
                        className="flex-1 p-2 rounded bg-black/40 border border-white/10 text-white text-xs"
                        placeholder="Milestone description"
                      />
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setNewMilestones([...newMilestones, ""])}
                  className="mt-2 text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                >
                  <Plus size={12} /> Add Milestone
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
                  Create Goal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
