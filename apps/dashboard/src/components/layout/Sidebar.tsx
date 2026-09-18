"use client";

import React, { useState } from "react";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquareCode,
  Network,
  Target,
  BrainCircuit,
  BookOpen,
  Bot,
  ShieldAlert,
  Wrench,
  History,
  LineChart,
  Settings,
  ChevronLeft,
  ChevronRight,
  Terminal,
} from "lucide-react";

interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  badge?: string | number;
  badgeVariant?: "default" | "warning" | "cyan";
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Core Console",
    items: [
      { name: "Overview", href: "/", icon: LayoutDashboard },
      { name: "Sessions", href: "/sessions", icon: MessageSquareCode, badge: "4" },
      { name: "Tasks", href: "/tasks", icon: Network, badge: "1 active", badgeVariant: "cyan" },
      { name: "Goals", href: "/goals", icon: Target },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { name: "Memory", href: "/memory", icon: BrainCircuit, badge: "5" },
      { name: "Knowledge", href: "/knowledge", icon: BookOpen },
      { name: "Agents", href: "/agents", icon: Bot, badge: "6" },
    ],
  },
  {
    label: "Governance & Safety",
    items: [
      {
        name: "Approvals",
        href: "/approvals",
        icon: ShieldAlert,
        badge: "2 pending",
        badgeVariant: "warning",
      },
      { name: "Tools", href: "/tools", icon: Wrench },
      { name: "Audit Logs", href: "/audit", icon: History },
    ],
  },
  {
    label: "System",
    items: [
      { name: "Analytics", href: "/analytics", icon: LineChart },
      { name: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`relative flex flex-col border-r border-white/10 bg-slate-950/80 backdrop-blur-2xl transition-all duration-300 z-30 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-white/10">
        <NextLink href="/" className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-slate-950 font-black text-sm shadow-md shadow-cyan-500/20 shrink-0">
            N
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-sm tracking-wider text-white font-mono leading-none">
                NEXUS
              </span>
              <span className="text-[10px] text-cyan-400 font-mono tracking-widest leading-tight mt-0.5">
                OS CONSOLE
              </span>
            </div>
          )}
        </NextLink>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition-colors hidden md:block"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Navigation Group Items */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {navGroups.map((group) => (
          <div key={group.label} className="space-y-1">
            {!collapsed && (
              <span className="px-3 text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500 block mb-1">
                {group.label}
              </span>
            )}
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);

              let badgeClasses = "bg-slate-800 text-slate-300 border-white/10";
              if (item.badgeVariant === "warning") {
                badgeClasses = "bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse";
              } else if (item.badgeVariant === "cyan") {
                badgeClasses = "bg-cyan-500/20 text-cyan-300 border-cyan-500/40";
              }

              return (
                <NextLink
                  key={item.name}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-mono font-medium transition-all group ${
                    isActive
                      ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/5"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent"
                  }`}
                  title={collapsed ? item.name : undefined}
                >
                  <Icon
                    size={16}
                    className={`shrink-0 transition-colors ${
                      isActive ? "text-cyan-400" : "text-slate-500 group-hover:text-slate-300"
                    }`}
                  />
                  {!collapsed && (
                    <span className="flex-1 truncate">{item.name}</span>
                  )}
                  {!collapsed && item.badge !== undefined && (
                    <span
                      className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono border ${badgeClasses}`}
                    >
                      {item.badge}
                    </span>
                  )}
                </NextLink>
              );
            })}
          </div>
        ))}
      </div>

      {/* Footer OS Context Status */}
      <div className="p-3 border-t border-white/10 bg-slate-950/90 text-slate-400 text-[11px] font-mono">
        {!collapsed ? (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-slate-500">
              <span>CORE KERNEL</span>
              <span className="text-emerald-400">ONLINE</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <Terminal size={13} className="text-cyan-400 shrink-0" />
              <span className="truncate">Port 8000 • WAL</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        )}
      </div>
    </aside>
  );
}
