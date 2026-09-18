import React from "react";
import type { FileDiffPreview } from "@nexus/types";

interface DiffViewerProps {
  diff?: FileDiffPreview;
  rawDiff?: string;
  filePath?: string;
}

export function DiffViewer({ diff, rawDiff, filePath }: DiffViewerProps) {
  const content = diff?.unified_diff || rawDiff || "";
  const path = diff?.file_path || filePath || "file.txt";
  const linesAdded = diff?.lines_added ?? 0;
  const linesRemoved = diff?.lines_removed ?? 0;

  const lines = content.split("\n");

  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/80 overflow-hidden text-xs font-mono">
      {/* File Header Bar */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900/80 border-b border-white/10">
        <div className="flex items-center gap-2 text-slate-300 truncate">
          <span className="text-slate-500">📄</span>
          <span className="font-medium text-cyan-400">{path}</span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-emerald-400">+{linesAdded}</span>
          <span className="text-rose-400">-{linesRemoved}</span>
        </div>
      </div>

      {/* Diff Content Body */}
      <div className="overflow-x-auto max-h-72 p-2.5 space-y-0.5 leading-5">
        {lines.length === 0 || !content ? (
          <div className="text-slate-500 italic p-2 text-center">
            No diff lines available
          </div>
        ) : (
          lines.map((line, idx) => {
            const isAdd = line.startsWith("+") && !line.startsWith("+++");
            const isDel = line.startsWith("-") && !line.startsWith("---");
            const isHunk = line.startsWith("@@");

            let lineBg = "hover:bg-white/5";
            let textColor = "text-slate-300";
            let indicator = " ";

            if (isAdd) {
              lineBg = "bg-emerald-500/10 text-emerald-300";
              textColor = "text-emerald-300";
              indicator = "+";
            } else if (isDel) {
              lineBg = "bg-rose-500/10 text-rose-300 line-through opacity-80";
              textColor = "text-rose-300";
              indicator = "-";
            } else if (isHunk) {
              lineBg = "bg-cyan-500/5 text-cyan-400 font-semibold";
              textColor = "text-cyan-400";
              indicator = "@";
            }

            return (
              <div
                key={idx}
                className={`flex items-start gap-3 px-2 py-0.5 rounded transition-colors ${lineBg}`}
              >
                <span className="w-8 text-right text-slate-600 select-none text-[10px]">
                  {idx + 1}
                </span>
                <span className="w-3 text-slate-500 select-none text-center">
                  {indicator}
                </span>
                <span className={`flex-1 whitespace-pre break-all ${textColor}`}>
                  {line}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
