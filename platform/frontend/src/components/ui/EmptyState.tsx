import React from "react";
import { Terminal, Sparkles } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description?: string;
}

export function EmptyState({
  title = "No Test Sessions Recorded Yet",
  description = "TraceReplay is connected to the backend. Start recording your AI applications or pytest suites to populate the dashboard.",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 p-12 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-500/20 bg-indigo-500/10 text-indigo-400 shadow-inner">
        <Sparkles className="h-7 w-7" />
      </div>

      <h3 className="mt-5 text-lg font-semibold text-zinc-100">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-zinc-400 leading-relaxed">
        {description}
      </p>

      <div className="mt-6 w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-left font-mono text-xs">
        <div className="flex items-center gap-2 text-zinc-400 pb-2 border-b border-zinc-800/80 mb-3">
          <Terminal className="h-3.5 w-3.5" />
          <span>Quickstart Recording Commands</span>
        </div>
        <div className="space-y-2 text-zinc-300">
          <p className="text-zinc-500"># 1. Record your pytest test suite</p>
          <p className="text-emerald-400 bg-emerald-950/30 p-2 rounded border border-emerald-800/30">
            pytest -v --trace-record
          </p>
          <p className="text-zinc-500 pt-2"># 2. Or sync existing local fixtures to the cloud</p>
          <p className="text-indigo-400 bg-indigo-950/30 p-2 rounded border border-indigo-800/30">
            tracereplay sync
          </p>
        </div>
      </div>
    </div>
  );
}
