"use client";

import React, { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Search, ShieldAlert, User, LogOut, LogIn } from "lucide-react";
import Link from "next/link";
import { useAuth } from "../../context/AuthContext";

interface TopCommandBarProps {
  onOpenCommand: () => void;
}

export function TopCommandBar({ onOpenCommand }: TopCommandBarProps) {
  const pathname = usePathname();
  const { user, isAuthenticated, logout } = useAuth();
  const [coreHealth, setCoreHealth] = useState<"online" | "degraded" | "checking">("checking");

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/health");
        if (res.ok) {
          const data = await res.json();
          setCoreHealth(data.status === "ok" ? "online" : "degraded");
        } else {
          setCoreHealth("degraded");
        }
      } catch {
        setCoreHealth("degraded");
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const getPageTitle = () => {
    if (pathname === "/") return "Overview Console";
    const segment = pathname.split("/")[1];
    return segment.charAt(0).toUpperCase() + segment.slice(1);
  };

  return (
    <header className="h-16 border-b border-white/10 bg-slate-950/60 backdrop-blur-xl px-6 flex items-center justify-between gap-4 z-20">
      {/* Location / Breadcrumb */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono text-slate-500 uppercase tracking-wider hidden sm:inline">
          NEXUS //
        </span>
        <h1 className="text-sm font-bold font-mono text-white tracking-wide">
          {getPageTitle()}
        </h1>
      </div>

      {/* Center Command Capsule */}
      <button
        onClick={onOpenCommand}
        className="flex items-center gap-3 px-4 py-2 rounded-full bg-slate-900/80 hover:bg-slate-800/90 border border-white/10 hover:border-cyan-500/40 text-slate-400 hover:text-slate-200 transition-all text-xs font-mono w-72 sm:w-96 shadow-inner"
      >
        <Search size={14} className="text-cyan-400 shrink-0" />
        <span className="flex-1 text-left truncate">Search or run command...</span>
        <kbd className="px-1.5 py-0.5 rounded bg-black/40 border border-white/10 text-[10px] text-slate-400">
          ⌘K
        </kbd>
      </button>

      {/* Right Telemetry & Status Badges */}
      <div className="flex items-center gap-3">
        {/* Core Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-white/10 text-xs font-mono">
          <span
            className={`w-2 h-2 rounded-full ${
              coreHealth === "online"
                ? "bg-emerald-400 animate-pulse"
                : "bg-amber-400"
            }`}
          />
          <span className="text-slate-300 text-[11px] uppercase">
            {coreHealth === "online" ? "API ONLINE" : "DEGRADED"}
          </span>
        </div>

        {/* Approvals Alert Button */}
        <Link
          href="/approvals"
          className="relative p-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 transition-colors"
          title="2 Pending Approvals"
        >
          <ShieldAlert size={16} />
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-slate-950 font-bold text-[10px] flex items-center justify-center font-mono animate-bounce">
            2
          </span>
        </Link>

        {/* User Identity Chip */}
        {isAuthenticated && user ? (
          <div className="flex items-center gap-2 pl-2 border-l border-white/10">
            <Link
              href="/settings"
              className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-white/10 text-xs font-mono text-slate-300 transition-colors"
              title="User Settings"
            >
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
              <User size={13} className="text-cyan-400" />
              <span className="max-w-[100px] truncate">
                {user.full_name || user.email.split("@")[0]}
              </span>
            </Link>
            <button
              onClick={() => logout()}
              className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
              title="Sign Out"
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-xs font-mono transition-colors"
          >
            <LogIn size={13} />
            <span>Sign In</span>
          </Link>
        )}
      </div>
    </header>
  );
}
