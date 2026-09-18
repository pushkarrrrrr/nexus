import React from "react";
import type { RiskLevel, TaskStatus } from "@nexus/types";

interface StatusBadgeProps {
  status?: TaskStatus | "online" | "offline" | "degraded" | "ready" | "cached" | "idle";
  risk?: RiskLevel;
  label?: string;
  size?: "sm" | "md";
  showDot?: boolean;
}

export function StatusBadge({
  status,
  risk,
  label,
  size = "sm",
  showDot = true,
}: StatusBadgeProps) {
  let text = label;
  let bg = "bg-slate-800/80";
  let border = "border-slate-700/60";
  let textColor = "text-slate-300";
  let dotColor = "bg-slate-400";
  let ping = false;

  if (risk) {
    text = text || risk;
    switch (risk) {
      case "LOW":
        bg = "bg-emerald-500/10";
        border = "border-emerald-500/30";
        textColor = "text-emerald-400";
        dotColor = "bg-emerald-400";
        break;
      case "MEDIUM":
        bg = "bg-amber-500/10";
        border = "border-amber-500/30";
        textColor = "text-amber-400";
        dotColor = "bg-amber-400";
        break;
      case "HIGH":
        bg = "bg-orange-500/10";
        border = "border-orange-500/30";
        textColor = "text-orange-400";
        dotColor = "bg-orange-400";
        ping = true;
        break;
      case "CRITICAL":
        bg = "bg-rose-500/15";
        border = "border-rose-500/40";
        textColor = "text-rose-400";
        dotColor = "bg-rose-400";
        ping = true;
        break;
    }
  } else if (status) {
    text = text || status.replace("_", " ").toUpperCase();
    switch (status) {
      case "completed":
      case "online":
      case "ready":
        bg = "bg-emerald-500/10";
        border = "border-emerald-500/30";
        textColor = "text-emerald-400";
        dotColor = "bg-emerald-400";
        break;
      case "executing":
        bg = "bg-cyan-500/10";
        border = "border-cyan-500/30";
        textColor = "text-cyan-400";
        dotColor = "bg-cyan-400";
        ping = true;
        break;
      case "planning":
      case "cached":
        bg = "bg-sky-500/10";
        border = "border-sky-500/30";
        textColor = "text-sky-400";
        dotColor = "bg-sky-400";
        break;
      case "awaiting_approval":
      case "degraded":
        bg = "bg-amber-500/10";
        border = "border-amber-500/30";
        textColor = "text-amber-400";
        dotColor = "bg-amber-400";
        ping = true;
        break;
      case "failed":
      case "offline":
        bg = "bg-rose-500/10";
        border = "border-rose-500/30";
        textColor = "text-rose-400";
        dotColor = "bg-rose-400";
        break;
      case "cancelled":
      case "pending":
      default:
        bg = "bg-slate-800/80";
        border = "border-slate-700/60";
        textColor = "text-slate-400";
        dotColor = "bg-slate-500";
        break;
    }
  }

  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[10px] gap-1.5"
      : "px-2.5 py-1 text-xs gap-2";

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded-full border ${bg} ${border} ${textColor} ${sizeClasses}`}
    >
      {showDot && (
        <span className="relative flex h-1.5 w-1.5">
          {ping && (
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full ${dotColor} opacity-75`}
            />
          )}
          <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${dotColor}`} />
        </span>
      )}
      <span>{text}</span>
    </span>
  );
}
