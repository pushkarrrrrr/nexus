"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
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
} from "lucide-react";

interface CommandModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CommandItem {
  id: string;
  title: string;
  category: string;
  href: string;
  icon: React.ElementType;
}

const commands: CommandItem[] = [
  { id: "overview", title: "Overview Dashboard", category: "Core", href: "/", icon: LayoutDashboard },
  { id: "sessions", title: "AI Sessions & Multi-Turn Context", category: "Core", href: "/sessions", icon: MessageSquareCode },
  { id: "tasks", title: "Active Tasks & DAG Visualizer", category: "Core", href: "/tasks", icon: Network },
  { id: "goals", title: "Autonomous Goal Management", category: "Core", href: "/goals", icon: Target },
  { id: "memory", title: "5-Class Memory Taxonomy Explorer", category: "Intelligence", href: "/memory", icon: BrainCircuit },
  { id: "knowledge", title: "Personal Knowledge Vector Base", category: "Intelligence", href: "/knowledge", icon: BookOpen },
  { id: "agents", title: "Specialized Multi-Agent Roster", category: "Intelligence", href: "/agents", icon: Bot },
  { id: "approvals", title: "Pending HITL Diff Approvals", category: "Governance", href: "/approvals", icon: ShieldAlert },
  { id: "tools", title: "Standardized Tool Capability Registry", category: "Governance", href: "/tools", icon: Wrench },
  { id: "audit", title: "Immutable Audit Ledger & Undo", category: "Governance", href: "/audit", icon: History },
  { id: "analytics", title: "Capstone Research Evaluation Benchmarks", category: "System", href: "/analytics", icon: LineChart },
  { id: "settings", title: "System & AI Gateway Configuration", category: "System", href: "/settings", icon: Settings },
];

export function CommandModal({ isOpen, onClose }: CommandModalProps) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onClose(); // toggle
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = commands.filter((cmd) =>
    cmd.title.toLowerCase().includes(query.toLowerCase()) ||
    cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (href: string) => {
    router.push(href);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-100">
      <div className="w-full max-w-xl glass-panel rounded-2xl border border-white/20 shadow-2xl overflow-hidden text-slate-200">
        {/* Search Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-white/10 bg-slate-900/60">
          <Search size={18} className="text-slate-400 mr-3" />
          <input
            type="text"
            placeholder="Type a command or jump to subsystem... (Esc to cancel)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-sm text-white font-mono placeholder-slate-500"
            autoFocus
          />
          <span className="px-1.5 py-0.5 text-[10px] font-mono text-slate-400 border border-white/10 rounded">
            ESC
          </span>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 font-mono">
              No matching commands or pages found.
            </div>
          ) : (
            filtered.map((cmd) => {
              const Icon = cmd.icon;
              return (
                <button
                  key={cmd.id}
                  onClick={() => handleSelect(cmd.href)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-left text-xs font-mono text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Icon size={16} className="text-cyan-400" />
                    <span>{cmd.title}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                    {cmd.category}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
