"use client";

import React, { useState, useEffect } from "react";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { MemoryItem, MemoryClass } from "@nexus/types";
import { mockMemories } from "../../src/mockData/mockMemories";
import {
  BrainCircuit,
  Trash2,
  Edit3,
  Plus,
  Search,
  Check,
  X,
  Tag,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

export default function MemoryPage() {
  const [memories, setMemories] = useState<MemoryItem[]>(mockMemories);
  const [selectedClass, setSelectedClass] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MemoryItem | null>(null);

  // New memory form state
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newClass, setNewClass] = useState<MemoryClass>("semantic");
  const [newTags, setNewTags] = useState("");

  const classes: { id: string; label: string; count?: number }[] = [
    { id: "all", label: "All Classes" },
    { id: "working", label: "Working" },
    { id: "conversational", label: "Conversational" },
    { id: "episodic", label: "Episodic" },
    { id: "semantic", label: "Semantic" },
    { id: "procedural", label: "Procedural" },
  ];

  // Fetch live memories from API on mount
  useEffect(() => {
    async function fetchMemories() {
      try {
        const token = localStorage.getItem("nexus_token");
        const res = await fetch("http://127.0.0.1:8000/api/v1/memory", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0) {
            setMemories(data);
          }
        }
      } catch {
        // Keep initial mock memories if API unreachable
      }
    }
    fetchMemories();
  }, []);

  const filtered = memories.filter((m) => {
    const matchesClass = selectedClass === "all" || m.memory_class === selectedClass;
    const matchesSearch =
      !searchQuery ||
      m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesClass && matchesSearch;
  });

  const handleToggle = async (id: string) => {
    setMemories((prev) =>
      prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m))
    );
    try {
      const token = localStorage.getItem("nexus_token");
      await fetch(`http://127.0.0.1:8000/api/v1/memory/${id}/toggle`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      // Optimistic update retained
    }
  };

  const handleDelete = async (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id));
    try {
      const token = localStorage.getItem("nexus_token");
      await fetch(`http://127.0.0.1:8000/api/v1/memory/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      // Optimistic update retained
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;

    const tagsArray = newTags
      .split(",")
      .map((t) => t.trim().replace(/^#/, ""))
      .filter(Boolean);

    const newItem: MemoryItem = {
      id: `mem_${Date.now()}`,
      title: newTitle,
      content: newContent,
      memory_class: newClass,
      confidence: 1.0,
      enabled: true,
      tags: tagsArray,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    setMemories([newItem, ...memories]);
    setIsCreateOpen(false);
    setNewTitle("");
    setNewContent("");
    setNewTags("");

    try {
      const token = localStorage.getItem("nexus_token");
      await fetch("http://127.0.0.1:8000/api/v1/memory", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          title: newItem.title,
          content: newItem.content,
          memory_class: newItem.memory_class,
          tags: newItem.tags,
          enabled: true,
        }),
      });
    } catch {
      // Local addition retained
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;

    setMemories((prev) =>
      prev.map((m) => (m.id === editingItem.id ? editingItem : m))
    );
    const target = editingItem;
    setEditingItem(null);

    try {
      const token = localStorage.getItem("nexus_token");
      await fetch(`http://127.0.0.1:8000/api/v1/memory/${target.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          title: target.title,
          content: target.content,
          memory_class: target.memory_class,
          tags: target.tags,
          confidence: target.confidence,
        }),
      });
    } catch {
      // Optimistic update retained
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white flex items-center gap-2">
            <BrainCircuit size={20} className="text-cyan-400" />
            5-Class Memory Taxonomy &amp; Knowledge
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Full user inspection, manual correction, provenance attribution, and category-level governance
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold font-mono text-xs transition-colors shadow-lg shadow-cyan-500/20"
          >
            <Plus size={14} />
            Add Memory
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Category Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono overflow-x-auto w-full md:w-auto">
          {classes.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedClass(c.id)}
              className={`px-3 py-1 rounded-md transition-colors whitespace-nowrap ${
                selectedClass === c.id
                  ? "bg-cyan-500 text-slate-950 font-bold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-72">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search memory content, tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </div>
      </div>

      {/* Grid of Memory Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((item) => (
          <Card
            key={item.id}
            title={
              <div className="flex items-center gap-2">
                <BrainCircuit size={16} className="text-cyan-400 shrink-0" />
                <span className="truncate">{item.title}</span>
              </div>
            }
            badge={<StatusBadge label={item.memory_class.toUpperCase()} status="planning" />}
            subtitle={`ID: ${item.id} • Confidence: ${(item.confidence * 100).toFixed(0)}%`}
            action={
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setEditingItem(item)}
                  className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                  title="Correct / Edit memory"
                >
                  <Edit3 size={13} />
                </button>
                <button
                  onClick={() => handleToggle(item.id)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                    item.enabled
                      ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                      : "bg-slate-800 border-white/10 text-slate-500"
                  }`}
                >
                  {item.enabled ? "ACTIVE" : "DISABLED"}
                </button>
                <button
                  onClick={() => handleDelete(item.id)}
                  className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition-colors"
                  title="Delete memory record"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            }
          >
            <p className="text-xs text-slate-300 font-mono leading-relaxed mb-4 whitespace-pre-wrap">
              {item.content}
            </p>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3 font-mono text-[11px] text-slate-400">
              <div className="flex items-center gap-1.5 flex-wrap">
                <Tag size={12} className="text-slate-500" />
                {item.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 rounded bg-slate-900 border border-white/5 text-[10px] text-slate-300"
                  >
                    #{tag}
                  </span>
                ))}
              </div>

              {item.source_session_id && (
                <span className="text-[10px] text-slate-500 truncate">
                  Session: {item.source_session_id}
                </span>
              )}
            </div>
          </Card>
        ))}

        {filtered.length === 0 && (
          <div className="col-span-full text-center py-12 border border-dashed border-white/10 rounded-xl">
            <BrainCircuit size={32} className="mx-auto text-slate-600 mb-2" />
            <p className="text-sm font-mono text-slate-400">No memories match current filter</p>
            <p className="text-xs font-mono text-slate-600 mt-1">
              Add a new memory item or adjust your search query
            </p>
          </div>
        )}
      </div>

      {/* Create Memory Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/15 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold font-mono text-white flex items-center gap-2">
                <Sparkles size={16} className="text-cyan-400" />
                Record New Memory
              </h3>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4 text-xs font-mono">
              <div>
                <label className="block text-slate-300 mb-1">Memory Class</label>
                <select
                  value={newClass}
                  onChange={(e) => setNewClass(e.target.value as MemoryClass)}
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="semantic">Semantic (Enduring facts, preferences)</option>
                  <option value="procedural">Procedural (How-to, execution recipes)</option>
                  <option value="episodic">Episodic (Historical run summaries)</option>
                  <option value="working">Working (Current session scratchpad)</option>
                  <option value="conversational">Conversational (Dialogue context)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Title</label>
                <input
                  type="text"
                  placeholder="e.g., Codebase Architecture Policy"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Content / Knowledge Fact</label>
                <textarea
                  rows={4}
                  placeholder="Exact description, instruction, or preference..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Tags (comma separated)</label>
                <input
                  type="text"
                  placeholder="architecture, policy, frontend"
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
                >
                  Save Memory
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit / Correct Memory Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/15 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold font-mono text-white flex items-center gap-2">
                <Edit3 size={16} className="text-cyan-400" />
                Correct Stored Memory
              </h3>
              <button
                onClick={() => setEditingItem(null)}
                className="text-slate-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4 text-xs font-mono">
              <div>
                <label className="block text-slate-300 mb-1">Title</label>
                <input
                  type="text"
                  value={editingItem.title}
                  onChange={(e) =>
                    setEditingItem({ ...editingItem, title: e.target.value })
                  }
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Content</label>
                <textarea
                  rows={4}
                  value={editingItem.content}
                  onChange={(e) =>
                    setEditingItem({ ...editingItem, content: e.target.value })
                  }
                  className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Memory Class</label>
                  <select
                    value={editingItem.memory_class}
                    onChange={(e) =>
                      setEditingItem({
                        ...editingItem,
                        memory_class: e.target.value as MemoryClass,
                      })
                    }
                    className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="semantic">Semantic</option>
                    <option value="procedural">Procedural</option>
                    <option value="episodic">Episodic</option>
                    <option value="working">Working</option>
                    <option value="conversational">Conversational</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 mb-1">Confidence (0.0 - 1.0)</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={editingItem.confidence}
                    onChange={(e) =>
                      setEditingItem({
                        ...editingItem,
                        confidence: parseFloat(e.target.value) || 1.0,
                      })
                    }
                    className="w-full bg-slate-800 border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
                >
                  Update Memory
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
