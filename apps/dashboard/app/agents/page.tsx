"use client";

import React from "react";
import { mockAgents } from "../../src/mockData/mockAgents";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { Bot, Cpu, ShieldCheck, Wrench } from "lucide-react";

export default function AgentsPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">Specialized Multi-Agent Roster</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Role-bounded autonomous workers communicating via structured Pydantic schemas
          </p>
        </div>
      </div>

      {/* Grid of Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {mockAgents.map((agent) => (
          <Card
            key={agent.id}
            title={
              <div className="flex items-center gap-2">
                <Bot size={16} className="text-cyan-400" />
                <span className="font-mono text-sm">{agent.name}</span>
              </div>
            }
            badge={<StatusBadge status={agent.status} />}
            subtitle={agent.role}
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
                  <span className="text-emerald-400 font-semibold">{agent.allowed_tools.length} Tools</span>
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

              {/* System Prompt Snippet */}
              <div>
                <span className="text-slate-500 text-[10px] uppercase block mb-1">
                  System Directive Constraint
                </span>
                <div className="p-2.5 rounded bg-black/50 border border-white/5 text-slate-400 italic text-[11px]">
                  &ldquo;{agent.system_prompt_preview}&rdquo;
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
