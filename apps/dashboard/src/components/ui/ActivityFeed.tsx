import React from "react";

export interface ActivityEventItem {
  id: string;
  timestamp: string;
  type: "tool" | "approval" | "system" | "dag" | "audit";
  title: string;
  description?: string;
  badge?: React.ReactNode;
}

interface ActivityFeedProps {
  events: ActivityEventItem[];
  maxItems?: number;
  className?: string;
}

export function ActivityFeed({ events, maxItems = 10, className = "" }: ActivityFeedProps) {
  const displayEvents = events.slice(0, maxItems);

  if (displayEvents.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-500 font-mono">
        No recent activity events recorded
      </div>
    );
  }

  return (
    <div className={`space-y-2.5 font-mono text-xs ${className}`}>
      {displayEvents.map((evt) => {
        let typeIcon = "✦";
        let typeColor = "text-cyan-400";
        if (evt.type === "approval") {
          typeIcon = "⚠️";
          typeColor = "text-amber-400";
        } else if (evt.type === "tool") {
          typeIcon = "⚡";
          typeColor = "text-sky-400";
        } else if (evt.type === "audit") {
          typeIcon = "🛡️";
          typeColor = "text-emerald-400";
        }

        return (
          <div
            key={evt.id}
            className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-900/50 border border-white/5 hover:border-white/10 transition-colors"
          >
            <span className={`text-xs mt-0.5 ${typeColor}`}>{typeIcon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-slate-200 truncate">
                  {evt.title}
                </span>
                <span className="text-[10px] text-slate-500 shrink-0">
                  {evt.timestamp}
                </span>
              </div>
              {evt.description && (
                <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                  {evt.description}
                </p>
              )}
            </div>
            {evt.badge && <div className="shrink-0">{evt.badge}</div>}
          </div>
        );
      })}
    </div>
  );
}
