import React from "react";
import clsx from "clsx";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  icon: LucideIcon;
  trend?: {
    value: string;
    isPositive?: boolean;
    label?: string;
  };
  accentColor?: "emerald" | "indigo" | "amber" | "cyan" | "rose";
  className?: string;
}

export function MetricCard({
  title,
  value,
  subValue,
  icon: Icon,
  trend,
  accentColor = "indigo",
  className,
}: MetricCardProps) {
  const accentGlow = {
    emerald: "from-emerald-500/10 via-transparent to-transparent text-emerald-400",
    indigo: "from-indigo-500/10 via-transparent to-transparent text-indigo-400",
    amber: "from-amber-500/10 via-transparent to-transparent text-amber-400",
    cyan: "from-cyan-500/10 via-transparent to-transparent text-cyan-400",
    rose: "from-rose-500/10 via-transparent to-transparent text-rose-400",
  };

  const iconBg = {
    emerald: "bg-emerald-950/80 text-emerald-400 border-emerald-800/50",
    indigo: "bg-indigo-950/80 text-indigo-400 border-indigo-800/50",
    amber: "bg-amber-950/80 text-amber-400 border-amber-800/50",
    cyan: "bg-cyan-950/80 text-cyan-400 border-cyan-800/50",
    rose: "bg-rose-950/80 text-rose-400 border-rose-800/50",
  };

  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900/90",
        className
      )}
    >
      <div
        className={clsx(
          "absolute -right-6 -top-6 h-28 w-28 rounded-full bg-linear-to-br blur-2xl",
          accentGlow[accentColor]
        )}
      />

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          {title}
        </span>
        <div
          className={clsx(
            "flex h-9 w-9 items-center justify-center rounded-lg border",
            iconBg[accentColor]
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold tracking-tight text-zinc-100">
          {value}
        </span>
        {subValue && (
          <span className="font-mono text-xs text-zinc-400">{subValue}</span>
        )}
      </div>

      {trend && (
        <div className="mt-3 flex items-center gap-1.5 text-xs">
          <span
            className={clsx(
              "font-mono font-medium",
              trend.isPositive ? "text-emerald-400" : "text-rose-400"
            )}
          >
            {trend.value}
          </span>
          {trend.label && (
            <span className="text-zinc-500">{trend.label}</span>
          )}
        </div>
      )}
    </div>
  );
}
