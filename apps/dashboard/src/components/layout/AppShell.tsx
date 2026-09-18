"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopCommandBar } from "./TopCommandBar";
import { CommandModal } from "./CommandModal";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [isCommandOpen, setIsCommandOpen] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#06090e] bg-grid-pattern text-slate-100">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopCommandBar onOpenCommand={() => setIsCommandOpen(true)} />

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8">
          {children}
        </main>
      </div>

      {/* Global Command Palette */}
      <CommandModal
        isOpen={isCommandOpen}
        onClose={() => setIsCommandOpen(false)}
      />
    </div>
  );
}
