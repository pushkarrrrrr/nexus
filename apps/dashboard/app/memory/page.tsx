"use client";

import React, { useState } from "react";
import { mockMemories } from "../../src/mockData/mockMemories";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import type { MemoryItem, MemoryClass } from "@nexus/types";
import { BrainCircuit, Trash2, Edit3, Shield, Tag } from "lucide-react";

export default function MemoryPage() {
  const [memories, setMemories] = useState<MemoryItem[]>(mockMemories);
  const [selectedClass, setSelectedClass] = useState<string>("all");

  const classes: { id: string; label: string }[] = [
    { id: "all", label: "All Classes" },
    { id: "semantic", label: "Semantic" },
    { id: "procedural", label: "Procedural" },
    { id: "episodic", label: "Episodic" },
    { id: "conversational", label: "Conversational" },
    { id: "working", label: "Working" },
  ];

  const filtered = memories.filter(
    (m) => selectedClass === "all" || m.memory_class === selectedClass
  );

  const toggleMemory = (id: string) => {
    setMemories((prev) =>
      prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m))
    );
  };

  const deleteMemory = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">5-Class Memory Taxonomy</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Full user inspection, provenance tracing, editing, and category-level toggle controls
          </p>
        </div>

        {/* Category Selector */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-900 border border-white/10 text-xs font-mono overflow-x-auto">
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
      </div>

      {/* Grid of Memory Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((item) => (
          <Card
            key={item.id}
            title={
              <div className="flex items-center gap-2">
                <BrainCircuit size={16} className="text-cyan-400" />
                <span className="truncate">{item.title}</span>
              </div>
            }
            badge={<StatusBadge label={item.memory_class.toUpperCase()} status="planning" />}
            subtitle={`ID: ${item.id} • Confidence: ${(item.confidence * 100).toFixed(0)}%`}
            action={
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleMemory(item.id)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                    item.enabled
                      ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                      : "bg-slate-800 border-white/10 text-slate-500"
                  }`}
                >
                  {item.enabled ? "ACTIVE" : "DISABLED"}
                </button>
                <button
                  onClick={() => deleteMemory(item.id)}
                  className="p-1 rounded hover:bg-rose-500/20 text-slate-500 hover:text-rose-400 transition-colors"
                  title="Delete memory record"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            }
          >
            <p className="text-xs text-slate-300 font-mono leading-relaxed mb-4">
              {item.content}
            </p>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3 font-mono text-[11px] text-slate-400">
              <div className="flex items-center gap-1.5">
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

              {item.source_turn_id && (
                <span className="text-[10px] text-slate-500 truncate">
                  Source: {item.source_turn_id}
                </span>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
