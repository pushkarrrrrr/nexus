import React from "react";

interface CardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
}

export function Card({
  title,
  subtitle,
  badge,
  action,
  children,
  className = "",
  glow = false,
}: CardProps) {
  return (
    <div
      className={`glass-panel rounded-xl p-5 relative overflow-hidden transition-all duration-200 border border-white/10 ${
        glow ? "glow-cyan border-cyan-500/30" : "hover:border-white/20"
      } ${className}`}
    >
      {(title || subtitle || badge || action) && (
        <div className="flex items-start justify-between gap-4 mb-4 border-b border-white/5 pb-3">
          <div>
            <div className="flex items-center gap-2.5">
              {typeof title === "string" ? (
                <h3 className="text-sm font-semibold text-slate-100 tracking-tight">
                  {title}
                </h3>
              ) : (
                title
              )}
              {badge}
            </div>
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}
