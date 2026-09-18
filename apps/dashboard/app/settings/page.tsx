"use client";

import React, { useState, useEffect } from "react";
import { Card } from "../../src/components/ui/Card";
import { Settings, Key, Shield, Database, Save, CheckCircle2, User, Globe } from "lucide-react";
import { useAuth } from "../../src/context/AuthContext";

export default function SettingsPage() {
  const { user, isAuthenticated, updatePreferences } = useAuth();

  const [defaultProvider, setDefaultProvider] = useState("openai");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [autoApproveLow, setAutoApproveLow] = useState(true);
  const [timezone, setTimezone] = useState("UTC");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (user?.preferences) {
      if (user.preferences.model_preferences?.default_provider) {
        setDefaultProvider(user.preferences.model_preferences.default_provider);
      }
      if (user.preferences.permission_preferences?.auto_grant_low_risk !== undefined) {
        setAutoApproveLow(user.preferences.permission_preferences.auto_grant_low_risk);
      }
      if (user.preferences.timezone) {
        setTimezone(user.preferences.timezone);
      }
    }
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSaving(true);

    try {
      if (isAuthenticated) {
        await updatePreferences({
          timezone,
          model_preferences: { default_provider: defaultProvider },
          permission_preferences: { auto_grant_low_risk: autoApproveLow },
        });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save preferences.");
      }
    } finally {
      setIsSaving(false);
    }
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
          <span>User preferences & system configuration successfully persisted.</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center gap-2">
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Operator Identity Card */}
        {isAuthenticated && user && (
          <Card
            title={
              <div className="flex items-center gap-2">
                <User size={16} className="text-cyan-400" />
                <span>Operator Identity & Context</span>
              </div>
            }
            subtitle="Authenticated account attributes and locale configuration"
          >
            <div className="space-y-4 font-mono text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-slate-400 mb-1">Operator Call-Sign</label>
                  <input
                    type="text"
                    disabled
                    value={user.full_name || "Unspecified"}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-white/10 text-slate-400 cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Email Address</label>
                  <input
                    type="text"
                    disabled
                    value={user.email}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-white/10 text-slate-400 cursor-not-allowed"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 flex items-center gap-1.5">
                  <Globe size={13} className="text-cyan-400" />
                  <span>Timezone</span>
                </label>
                <input
                  type="text"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="e.g. UTC, America/New_York, Asia/Kolkata"
                  className="w-full p-2.5 rounded-lg bg-slate-900 border border-white/10 text-white outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          </Card>
        )}

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
