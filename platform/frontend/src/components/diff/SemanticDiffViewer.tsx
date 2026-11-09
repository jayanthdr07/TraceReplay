"use client";

import React from "react";
import { GitCompare, CheckCircle2, AlertTriangle } from "lucide-react";

interface SemanticDiffViewerProps {
  expectedText: string;
  actualText: string;
  similarityScore?: number;
  threshold?: number;
}

export function SemanticDiffViewer({
  expectedText,
  actualText,
  similarityScore = 1.0,
  threshold = 0.85,
}: SemanticDiffViewerProps) {
  const isPassing = similarityScore >= threshold;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
        <div className="flex items-center gap-2.5">
          <GitCompare className="h-5 w-5 text-indigo-400" />
          <h3 className="text-base font-semibold text-zinc-100">
            Semantic Diff & Drift Inspector
          </h3>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-400 font-mono">
            Threshold: {(threshold * 100).toFixed(0)}%
          </span>
          <div
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs font-semibold ${isPassing
                ? "border-emerald-800 bg-emerald-950/70 text-emerald-300"
                : "border-rose-800 bg-rose-950/70 text-rose-300"
              }`}
          >
            {isPassing ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
            )}
            <span>{(similarityScore * 100).toFixed(1)}% Match</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mt-6">
        {/* Expected Fixture Column */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800 mb-3">
            <span className="font-mono text-xs font-semibold text-zinc-300">
              Recorded Baseline Fixture
            </span>
            <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400 font-mono">
              Expected
            </span>
          </div>
          <pre className="font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
            {expectedText}
          </pre>
        </div>

        {/* Actual Replay Output Column */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800 mb-3">
            <span className="font-mono text-xs font-semibold text-zinc-300">
              Actual Replayed Response
            </span>
            <span className="rounded bg-indigo-950 text-indigo-300 border border-indigo-800/80 px-2 py-0.5 text-[10px] font-mono">
              Actual
            </span>
          </div>
          <pre className="font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
            {actualText}
          </pre>
        </div>
      </div>
    </div>
  );
}
