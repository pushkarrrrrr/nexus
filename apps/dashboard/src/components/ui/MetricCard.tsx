import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subvalue?: string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}

export function MetricCard({
  label,
  value,
  subvalue,
  change,
  trend = "neutral",
  icon,
}: MetricCardProps) {
  let trendColor = "text-slate-400";
  if (trend === "up") trendColor = "text-emerald-400";
  if (trend === "down") trendColor = "text-rose-400";

  return (
    <div className="glass-panel p-4 rounded-xl border border-white/10 hover:border-white/20 transition-all">
      <div className="flex items-center justify-between text-slate-400 text-xs font-mono uppercase tracking-wider mb-2">
        <span>{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xl font-bold font-mono text-white tracking-tight">
          {value}
        </span>
        {change && (
          <span className={`text-xs font-mono font-medium ${trendColor}`}>
            {change}
          </span>
        )}
      </div>
      {subvalue && (
        <p className="text-xs text-slate-500 font-mono mt-1 truncate">
          {subvalue}
        </p>
      )}
    </div>
  );
}
