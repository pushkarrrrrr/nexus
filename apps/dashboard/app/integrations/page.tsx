"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card } from "../../src/components/ui/Card";
import { StatusBadge } from "../../src/components/ui/StatusBadge";
import { useAuth } from "../../src/context/AuthContext";
import {
  Globe,
  GitPullRequest,
  Mail,
  Calendar,
  Key,
  RefreshCw,
  Play,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Lock,
  Layers,
  Apple,
  Monitor,
} from "lucide-react";

interface IntegrationStatus {
  provider: string;
  status: string;
  is_enabled: boolean;
  last_sync_at: string | null;
  metadata: Record<string, unknown>;
}

interface MacOSPermissions {
  is_macos: boolean;
  platform: string;
  executable_path: string;
  accessibility_trusted: boolean;
  screen_capture_allowed: boolean;
  all_permissions_granted: boolean;
  settings_urls: {
    accessibility: string;
    screen_capture: string;
  };
  diagnostics: Record<string, string>;
}

interface MacOSApp {
  app_name: string;
  bundle_id: string;
  pid: number;
  is_frontmost: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function IntegrationsPage() {
  const { token } = useAuth();
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([
    { provider: "browser", status: "ACTIVE", is_enabled: true, last_sync_at: null, metadata: {} },
    { provider: "github", status: "DISCONNECTED", is_enabled: false, last_sync_at: null, metadata: {} },
    { provider: "google", status: "DISCONNECTED", is_enabled: false, last_sync_at: null, metadata: {} },
    { provider: "macos", status: "ACTIVE", is_enabled: true, last_sync_at: null, metadata: {} },
  ]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form states
  const [githubToken, setGithubToken] = useState("");
  const [googleToken, setGoogleToken] = useState("");
  const [loginUrl, setLoginUrl] = useState("https://web.whatsapp.com");
  const [isConnecting, setIsConnecting] = useState<string | null>(null);

  // macOS states
  const [macosPermissions, setMacosPermissions] = useState<MacOSPermissions | null>(null);
  const [macosApps, setMacosApps] = useState<MacOSApp[]>([]);
  const [isLoadingApps, setIsLoadingApps] = useState<boolean>(false);

  const fetchIntegrations = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setIntegrations(data);
        }
      }
    } catch {
      // Keep initial default state if offline
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  const fetchMacosPermissions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/macos/permissions`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setMacosPermissions(data);
      }
    } catch {
      // offline fallback
    }
  }, [token]);

  const fetchMacosApps = useCallback(async () => {
    setIsLoadingApps(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/macos/apps`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setMacosApps(data.apps || []);
      }
    } catch {
      // offline fallback
    } finally {
      setIsLoadingApps(false);
    }
  }, [token]);

  useEffect(() => {
    fetchIntegrations();
    fetchMacosPermissions();
    fetchMacosApps();
  }, [fetchIntegrations, fetchMacosPermissions, fetchMacosApps]);


  const handleConnect = async (provider: string, tokenVal: string) => {
    setIsConnecting(provider);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${provider}/connect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ token: tokenVal }),
      });
      if (res.ok) {
        setActionMessage({
          type: "success",
          text: `Successfully authenticated and connected ${provider.toUpperCase()}.`,
        });
        await fetchIntegrations();
      } else {
        const err = await res.json();
        setActionMessage({
          type: "error",
          text: err.detail || `Failed to connect ${provider}.`,
        });
      }
    } catch (e: unknown) {
      setActionMessage({
        type: "error",
        text: `Connection request failed: ${e instanceof Error ? e.message : String(e)}`,
      });
    } finally {
      setIsConnecting(null);
    }
  };

  const handleDisconnect = async (provider: string) => {
    setIsConnecting(provider);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${provider}/disconnect`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        setActionMessage({
          type: "success",
          text: `Disconnected ${provider.toUpperCase()} credentials purged.`,
        });
        await fetchIntegrations();
      }
    } catch (e: unknown) {
      setActionMessage({
        type: "error",
        text: `Disconnect failed: ${e instanceof Error ? e.message : String(e)}`,
      });
    } finally {
      setIsConnecting(null);
    }
  };

  const handleTestHealth = async (provider: string) => {
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${provider}/health`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (res.ok && data.status === "healthy") {
        setActionMessage({
          type: "success",
          text: `${provider.toUpperCase()} health check passed: Healthy connection active.`,
        });
      } else {
        setActionMessage({
          type: "error",
          text: `${provider.toUpperCase()} health check: ${data.error || data.status || "Unreachable"}`,
        });
      }
    } catch (e: unknown) {
      setActionMessage({
        type: "error",
        text: `Health check error: ${e instanceof Error ? e.message : String(e)}`,
      });
    }
  };

  const handleLaunchLoginSession = async () => {
    setActionMessage(null);
    setIsConnecting("browser_launch");
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/browser/login-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ url: loginUrl, timeout_seconds: 180 }),
      });
      if (res.ok) {
        const data = await res.json();
        setActionMessage({
          type: "success",
          text: data.message || "Visible persistent browser window launched. Complete your manual login.",
        });
      } else {
        const err = await res.json();
        setActionMessage({
          type: "error",
          text: err.detail || "Failed to launch login session.",
        });
      }
    } catch (e: unknown) {
      setActionMessage({
        type: "error",
        text: `Launch failed: ${e instanceof Error ? e.message : String(e)}`,
      });
    } finally {
      setIsConnecting(null);
    }
  };

  const getStatus = (provider: string): IntegrationStatus => {
    return (
      integrations.find((i) => i.provider === provider) || {
        provider,
        status: "DISCONNECTED",
        is_enabled: false,
        last_sync_at: null,
        metadata: {},
      }
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold font-mono text-white">External Integrations & Connectors</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-bold">
              Phase 13
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Persistent browser sessions, GitHub API, and Google Workspace connectors with AES-256-GCM encryption and policy risk gating
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchIntegrations}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/10 hover:border-cyan-500/40 bg-white/5 hover:bg-white/10 text-xs font-mono text-slate-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Action notification banner */}
      {actionMessage && (
        <div
          className={`flex items-center gap-3 p-3 rounded-lg border text-xs font-mono ${
            actionMessage.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-rose-500/10 border-rose-500/30 text-rose-400"
          }`}
        >
          {actionMessage.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
          )}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* Integration Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. Browser Automation Card */}
        <Card className="p-6 border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                  <Globe className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-white text-base">Browser Automation</h3>
                  <p className="text-xs text-slate-400 font-mono">Playwright Persistent Profiles</p>
                </div>
              </div>
              <StatusBadge status={getStatus("browser").status} />
            </div>

            <p className="text-xs text-slate-300 font-mono leading-relaxed">
              Maintains session isolation at <code className="text-cyan-300 bg-cyan-950/40 px-1 py-0.5 rounded">~/.nexus/browser_profiles/</code> with 0700 POSIX permissions. Retains cookies, LocalStorage, and IndexedDB across agent invocations.
            </p>

            <div className="space-y-2 pt-2 border-t border-white/5">
              <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                Target Login URL (QR / 2FA / SPA)
              </label>
              <input
                type="text"
                value={loginUrl}
                onChange={(e) => setLoginUrl(e.target.value)}
                placeholder="https://web.whatsapp.com"
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-white/10 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50"
              />
            </div>
          </div>

          <div className="pt-6 space-y-2">
            <button
              onClick={handleLaunchLoginSession}
              disabled={isConnecting === "browser_launch"}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs transition-colors shadow-lg shadow-cyan-500/20"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {isConnecting === "browser_launch" ? "Launching Browser..." : "Launch Persistent Login Session"}
            </button>
            <button
              onClick={() => handleTestHealth("browser")}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 bg-white/5 text-xs font-mono text-slate-300"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Check Session Health
            </button>
          </div>
        </Card>

        {/* 2. GitHub Integration Card */}
        <Card className="p-6 border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
                  <GitPullRequest className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-white text-base">GitHub</h3>
                  <p className="text-xs text-slate-400 font-mono">Issues, Pull Requests, Code</p>
                </div>
              </div>
              <StatusBadge status={getStatus("github").status} />
            </div>

            <p className="text-xs text-slate-300 font-mono leading-relaxed">
              Provides repository inspection, issue creation, and pull request generation. Tokens are encrypted at rest via AES-256-GCM. Mutating operations strictly enforce human approval.
            </p>

            <div className="space-y-2 pt-2 border-t border-white/5">
              <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Key className="w-3 h-3 text-purple-400" />
                Personal Access Token (PAT)
              </label>
              <input
                type="password"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-white/10 text-xs font-mono text-slate-200 focus:outline-none focus:border-purple-500/50"
              />
            </div>
          </div>

          <div className="pt-6 space-y-2">
            <div className="flex gap-2">
              <button
                onClick={() => handleConnect("github", githubToken)}
                disabled={!githubToken || isConnecting === "github"}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-mono font-bold text-xs transition-colors"
              >
                <Lock className="w-3.5 h-3.5" />
                {isConnecting === "github" ? "Connecting..." : "Connect GitHub"}
              </button>
              {getStatus("github").status === "ACTIVE" && (
                <button
                  onClick={() => handleDisconnect("github")}
                  className="px-3 py-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-mono text-xs"
                >
                  Disconnect
                </button>
              )}
            </div>
            <button
              onClick={() => handleTestHealth("github")}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 bg-white/5 text-xs font-mono text-slate-300"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Verify GitHub Token
            </button>
          </div>
        </Card>

        {/* 3. Google Workspace Card */}
        <Card className="p-6 border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
                  <Mail className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-white text-base">Google Workspace</h3>
                  <p className="text-xs text-slate-400 font-mono">Gmail & Google Calendar</p>
                </div>
              </div>
              <StatusBadge status={getStatus("google").status} />
            </div>

            <p className="text-xs text-slate-300 font-mono leading-relaxed">
              Provides email search, email composition, and calendar scheduling tools. Outbound email sending and event creation require human-in-the-loop verification.
            </p>

            <div className="space-y-2 pt-2 border-t border-white/5">
              <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Key className="w-3 h-3 text-amber-400" />
                OAuth / Bearer Access Token
              </label>
              <input
                type="password"
                value={googleToken}
                onChange={(e) => setGoogleToken(e.target.value)}
                placeholder="ya29.xxxxxxxxxxxxxxxxxxxx"
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-white/10 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500/50"
              />
            </div>
          </div>

          <div className="pt-6 space-y-2">
            <div className="flex gap-2">
              <button
                onClick={() => handleConnect("google", googleToken)}
                disabled={!googleToken || isConnecting === "google"}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-mono font-bold text-xs transition-colors"
              >
                <Lock className="w-3.5 h-3.5" />
                {isConnecting === "google" ? "Connecting..." : "Connect Google"}
              </button>
              {getStatus("google").status === "ACTIVE" && (
                <button
                  onClick={() => handleDisconnect("google")}
                  className="px-3 py-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-mono text-xs"
                >
                  Disconnect
                </button>
              )}
            </div>
            <button
              onClick={() => handleTestHealth("google")}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 bg-white/5 text-xs font-mono text-slate-300"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Verify Google Token
            </button>
          </div>
        </Card>

        {/* 4. Native macOS Control Card */}
        <Card className="p-6 border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
                  <Apple className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-white text-base">Native macOS Control</h3>
                  <p className="text-xs text-slate-400 font-mono">Accessibility (AX) & Quartz Engine</p>
                </div>
              </div>
              <StatusBadge status={getStatus("macos").status} />
            </div>

            <p className="text-xs text-slate-300 font-mono leading-relaxed">
              Direct desktop automation via JXA Accessibility tree inspection, synthetic CoreGraphics input injection, and native window frame capture.
            </p>

            {/* TCC Permissions Diagnostics */}
            <div className="space-y-2 pt-2 border-t border-white/5">
              <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                  TCC System Permissions
                </span>
                <span className="text-[10px] text-slate-500">{macosPermissions?.platform || "Darwin"}</span>
              </div>

              <div className="space-y-1.5 text-xs font-mono">
                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/80 border border-white/5">
                  <span className="text-slate-300">Accessibility (AX)</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    macosPermissions?.accessibility_trusted
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                  }`}>
                    {macosPermissions?.accessibility_trusted ? "Trusted" : "Missing Trust"}
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-950/80 border border-white/5">
                  <span className="text-slate-300">Screen Recording</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    macosPermissions?.screen_capture_allowed
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                  }`}>
                    {macosPermissions?.screen_capture_allowed ? "Allowed" : "Missing"}
                  </span>
                </div>
              </div>

              {!macosPermissions?.all_permissions_granted && (
                <a
                  href={macosPermissions?.settings_urls?.accessibility || "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"}
                  className="flex items-center justify-center gap-1.5 w-full py-1.5 px-2 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-300 font-mono text-[11px] transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open System Settings to Grant Permissions
                </a>
              )}
            </div>

            {/* Running Applications Quick Inspector */}
            <div className="space-y-2 pt-2 border-t border-white/5">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Monitor className="w-3.5 h-3.5 text-cyan-400" />
                  Running Desktop Apps ({macosApps.length})
                </span>
                <button
                  onClick={fetchMacosApps}
                  disabled={isLoadingApps}
                  className="hover:text-white p-1 rounded transition-colors"
                  title="Refresh Running Apps"
                >
                  <RefreshCw className={`w-3 h-3 ${isLoadingApps ? "animate-spin" : ""}`} />
                </button>
              </div>
              {macosApps.length > 0 && (
                <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
                  {macosApps.slice(0, 6).map((app, idx) => (
                    <span
                      key={idx}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                        app.is_frontmost
                          ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                          : "bg-slate-950 text-slate-400 border-white/5"
                      }`}
                    >
                      {app.app_name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="pt-6 space-y-2">
            <div className="flex gap-2">
              <button
                onClick={() => handleConnect("macos", "")}
                disabled={isConnecting === "macos"}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-mono font-bold text-xs transition-colors"
              >
                <Apple className="w-3.5 h-3.5" />
                {isConnecting === "macos" ? "Verifying..." : "Connect macOS Native"}
              </button>
              {getStatus("macos").status === "ACTIVE" && (
                <button
                  onClick={() => handleDisconnect("macos")}
                  className="px-3 py-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-mono text-xs"
                >
                  Disconnect
                </button>
              )}
            </div>
            <button
              onClick={() => handleTestHealth("macos")}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 bg-white/5 text-xs font-mono text-slate-300"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Verify macOS Health
            </button>
          </div>
        </Card>
      </div>

      {/* Safety & Policy Overview Card */}
      <Card className="p-6 border-white/10 bg-slate-950/40">
        <div className="flex items-center gap-3 mb-4">
          <Layers className="w-5 h-5 text-cyan-400" />
          <h4 className="font-mono font-bold text-white text-sm">Policy & Safety Enforcements</h4>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono text-slate-400">
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <div className="text-slate-200 font-bold mb-1 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              Autonomous (LOW Risk)
            </div>
            <p>browser.open_login_session, browser.navigate, browser.get_snapshot, github.list_issues, github.read_file, google.list_calendar_events, google.search_gmail, macos.list_running_apps, macos.focus_app, macos.inspect_ui, macos.capture_window</p>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <div className="text-slate-200 font-bold mb-1 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              Gated (HIGH Risk)
            </div>
            <p>browser.click, browser.type, github.create_issue, github.create_pr, google.create_calendar_event, google.send_email, macos.click_element, macos.type_text, macos.send_shortcut</p>
          </div>
          <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <div className="text-slate-200 font-bold mb-1 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
              SSRF Hardening
            </div>
            <p>Strict IP resolver rejects loopback (127.0.0.0/8, ::1), private RFC 1918 subnets, and cloud metadata endpoints (169.254.169.254).</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
