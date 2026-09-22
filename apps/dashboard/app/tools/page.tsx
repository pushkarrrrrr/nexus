"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { mockTools } from "../../src/mockData/mockTools";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { useAuth } from "../../src/context/AuthContext";
import type { RiskLevel } from "@nexus/types";
import {
  Wrench,
  Undo2,
  Search,
  RefreshCw,
  Clock,
  ShieldAlert,
  Code2,
  Layers,
  Globe,
} from "lucide-react";

interface DisplayTool {
  name: string;
  description: string;
  required_capability: string;
  default_risk_level: RiskLevel | string;
  timeout_seconds: number;
  is_reversible: boolean;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ToolsPage() {
  const { token } = useAuth();
  const [tools, setTools] = useState<DisplayTool[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [search, setSearch] = useState("");
  const [selectedSchema, setSelectedSchema] = useState<string | null>(null);

  const fetchTools = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/tools`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        const data = await res.json();
        if (data.items && Array.isArray(data.items)) {
          setTools(data.items);
          setIsLoading(false);
          return;
        }
      }
      throw new Error("Using fallback mock tools");
    } catch {
      const mappedMocks: DisplayTool[] = mockTools.map((m) => ({
        name: m.name,
        description: m.description,
        required_capability: m.name,
        default_risk_level: m.risk_level,
        timeout_seconds: 30.0,
        is_reversible: m.reversibility,
        input_schema: m.input_schema,
        output_schema: m.output_schema,
      }));
      setTools(mappedMocks);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  const filtered = tools.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase()) ||
      t.required_capability.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">Tool Capability Registry</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-bold">
              {tools.length} Tools Active
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Strictly typed capability manifests with risk tiers, policy gating, and side-effect rollback specifications
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

          <button
            onClick={fetchTools}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-white/10 font-mono text-xs transition-colors"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Integrations Bridge Banner */}
      <div className="flex items-center justify-between p-3.5 rounded-xl border border-cyan-500/20 bg-cyan-500/5 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-mono font-bold text-white">External Integrations Active</span>
            <p className="text-[11px] font-mono text-slate-400">
              Manage Browser Automation, GitHub, and Google Workspace sessions in the cockpit.
            </p>
          </div>
        </div>
        <Link
          href="/integrations"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-xs font-mono font-bold text-cyan-300 transition-colors"
        >
          Manage Integrations &rarr;
        </Link>
      </div>

      {/* Grid of Tools */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filtered.map((tool) => (
          <Card
            key={tool.name}
            title={
              <div className="flex items-center gap-2">
                <Wrench size={16} className="text-cyan-400" />
                <span className="font-mono text-sm font-semibold">{tool.name}</span>
              </div>
            }
            badge={<StatusBadge risk={tool.default_risk_level as RiskLevel} />}
            subtitle={
              <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
                <span className="text-cyan-400">Req: {tool.required_capability}</span>
                <span className="flex items-center gap-1 text-slate-500">
                  <Clock size={11} /> {tool.timeout_seconds}s timeout
                </span>
              </div>
            }
            action={
              tool.is_reversible ? (
                <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  <Undo2 size={11} /> REVERSIBLE
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-white/5">
                  PERMANENT
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
                  <pre className="p-2.5 rounded bg-black/50 border border-white/5 text-cyan-300 text-[11px] overflow-x-auto max-h-48">
                    {JSON.stringify(tool.input_schema, null, 2)}
                  </pre>
                </div>

                <div>
                  <span className="text-slate-500 text-[10px] uppercase block mb-1">
                    Output Schema
                  </span>
                  <pre className="p-2.5 rounded bg-black/50 border border-white/5 text-emerald-300 text-[11px] overflow-x-auto max-h-36">
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
