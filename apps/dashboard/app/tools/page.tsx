"use client";

import React, { useState } from "react";
import { mockTools } from "../../src/mockData/mockTools";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { Wrench, Shield, Undo2, Search, FileCode } from "lucide-react";

export default function ToolsPage() {
  const [search, setSearch] = useState("");

  const filtered = mockTools.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Tool Capability Registry</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Strictly typed capability manifests with risk tiers and rollback specifications
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-white/10 w-64">
            <Search size={14} className="text-slate-400" />
            <input
              type="text"
              placeholder="Search capabilities..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-transparent border-none outline-none text-xs font-mono text-white placeholder-slate-500 w-full"
            />
          </div>
        </div>
      </div>

      {/* Grid of Tools */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filtered.map((tool) => (
          <Card
            key={tool.name}
            title={
              <div className="flex items-center gap-2">
                <Wrench size={16} className="text-cyan-400" />
                <span className="font-mono text-sm">{tool.name}</span>
              </div>
            }
            badge={<StatusBadge risk={tool.risk_level} />}
            subtitle={`Action: ${tool.action_type}`}
            action={
              tool.reversibility ? (
                <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  <Undo2 size={11} /> REVERSIBLE
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-white/5">
                  IRREVERSIBLE
                </span>
              )
            }
          >
            <div className="space-y-4 font-mono text-xs">
              <p className="text-slate-300 leading-relaxed text-[12px]">
                {tool.description}
              </p>

              {/* Schemas */}
              <div className="space-y-2 border-t border-white/5 pt-3">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block mb-1">
                    Input Schema (JSON Schema)
                  </span>
                  <pre className="p-2.5 rounded bg-black/50 border border-white/5 text-cyan-300 text-[11px] overflow-x-auto">
                    {JSON.stringify(tool.input_schema, null, 2)}
                  </pre>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] uppercase block mb-1">
                    Output Schema
                  </span>
                  <pre className="p-2.5 rounded bg-black/50 border border-white/5 text-emerald-300 text-[11px] overflow-x-auto">
                    {JSON.stringify(tool.output_schema, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
