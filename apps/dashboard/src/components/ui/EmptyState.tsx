import React from "react";

interface EmptyStateProps {
  icon?: string | React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon = "📂",
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl border border-dashed border-white/10 bg-slate-950/40">
      <div className="text-3xl mb-3 text-slate-500">{icon}</div>
      <h3 className="text-sm font-semibold text-slate-200 mb-1 font-mono">
        {title}
      </h3>
      <p className="text-xs text-slate-400 max-w-sm mb-4 font-mono">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="px-3.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-mono font-medium transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function LoadingState({ message = "Loading telemetry data..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <div className="w-6 h-6 border-2 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin mb-3" />
      <span className="text-xs font-mono text-slate-400 animate-pulse">
        {message}
      </span>
    </div>
  );
}
