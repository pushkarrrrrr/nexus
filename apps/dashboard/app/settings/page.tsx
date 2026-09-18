"use client";

import React, { useState } from "react";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { Settings, Key, Shield, Database, Save, CheckCircle2 } from "lucide-react";

export default function SettingsPage() {
  const [defaultProvider, setDefaultProvider] = useState("openai");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [autoApproveLow, setAutoApproveLow] = useState(true);
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 4000);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <h2 className="text-xl font-bold font-mono text-white">System &amp; Gateway Settings</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Model-provider agnostic AI Gateway, policy risk parameters, and database targets
          </p>
        </div>
      </div>

      {saved && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
          <CheckCircle2 size={16} className="shrink-0" />
          <span>System configuration successfully updated in memory.</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Multi-Model AI Gateway Card */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Key size={16} className="text-cyan-400" />
              <span>Multi-Provider AI Gateway</span>
            </div>
          }
          subtitle="Configure upstream model providers (Never hardcode models into business logic)"
        >
          <div className="space-y-4 font-mono text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Default Reasoning Provider</label>
              <select
                value={defaultProvider}
                onChange={(e) => setDefaultProvider(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-900 border border-white/10 text-white outline-none focus:border-cyan-500"
              >
                <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                <option value="gemini">Google (Gemini 1.5 Pro / Flash)</option>
                <option value="ollama">Local / Ollama (Offline Llama 3)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Local Ollama Base URL</label>
              <input
                type="text"
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-slate-900 border border-white/10 text-white outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </Card>

        {/* Policy & Safety Governance Card */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Shield size={16} className="text-amber-400" />
              <span>Policy &amp; Safety Parameters</span>
            </div>
          }
          subtitle="Granular risk tier thresholds and Human-in-the-Loop gating"
        >
          <div className="space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-white/5">
              <div>
                <span className="text-white font-bold block">
                  Auto-Approve LOW Risk Actions
                </span>
                <span className="text-slate-400 text-[11px]">
                  Automatically allow non-destructive reads (filesystem.read, searching docs)
                </span>
              </div>
              <input
                type="checkbox"
                checked={autoApproveLow}
                onChange={(e) => setAutoApproveLow(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 text-cyan-500 focus:ring-0"
              />
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-white/5">
              <div>
                <span className="text-white font-bold block">
                  Session Permission Cache Expiry
                </span>
                <span className="text-slate-400 text-[11px]">
                  Maximum duration before session grants expire (Hours)
                </span>
              </div>
              <span className="text-cyan-400 font-bold">24 Hours</span>
            </div>
          </div>
        </Card>

        {/* Database & Storage Card */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Database size={16} className="text-emerald-400" />
              <span>Database Engine</span>
            </div>
          }
          subtitle="PostgreSQL with pgvector &amp; SQLite WAL fallback"
        >
          <div className="space-y-2 font-mono text-xs text-slate-300">
            <div className="flex justify-between p-2 rounded bg-slate-900">
              <span className="text-slate-500">Active Storage Driver:</span>
              <span className="text-emerald-400 font-bold">SQLite (WAL Mode)</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-900">
              <span className="text-slate-500">Snapshot Vault Path:</span>
              <span>.nexus/snapshots/</span>
            </div>
          </div>
        </Card>

        <div className="flex justify-end">
          <button
            type="submit"
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs transition-colors shadow-lg shadow-cyan-500/20"
          >
            <Save size={14} /> Save Configuration
          </button>
        </div>
      </form>
    </div>
  );
}
