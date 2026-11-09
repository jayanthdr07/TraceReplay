import React from "react";
import clsx from "clsx";
import { SessionMode, SessionStatus } from "@/types/api";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "danger" | "warning" | "info" | "purple";
  size?: "sm" | "md";
  className?: string;
}

export function Badge({
  children,
  variant = "default",
  size = "md",
  className,
}: BadgeProps) {
  const variantStyles = {
    default: "bg-zinc-800 text-zinc-300 border-zinc-700",
    success: "bg-emerald-950/70 text-emerald-300 border-emerald-800/80",
    danger: "bg-rose-950/70 text-rose-300 border-rose-800/80",
    warning: "bg-amber-950/70 text-amber-300 border-amber-800/80",
    info: "bg-cyan-950/70 text-cyan-300 border-cyan-800/80",
    purple: "bg-indigo-950/70 text-indigo-300 border-indigo-800/80",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-xs font-medium",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border font-mono tracking-tight transition-colors",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: SessionStatus }) {
  if (status === "passed") {
    return (
      <Badge variant="success">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        PASSED
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="danger">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
        FAILED
      </Badge>
    );
  }
  return (
    <Badge variant="purple">
      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
      RECORDED
    </Badge>
  );
}

export function ModeBadge({ mode }: { mode: SessionMode }) {
  switch (mode) {
    case "replay":
      return <Badge variant="success">⚡ REPLAY</Badge>;
    case "record":
      return <Badge variant="purple">⏺ RECORD</Badge>;
    case "passthrough":
      return <Badge variant="warning">🌐 LIVE PASSTHROUGH</Badge>;
    default:
      return <Badge variant="info">🤖 AUTO</Badge>;
  }
}
