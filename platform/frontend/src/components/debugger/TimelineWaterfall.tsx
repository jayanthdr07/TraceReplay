"use client";

import React from "react";
import { Interaction } from "@/types/api";
import { Clock, Wrench } from "lucide-react";

interface TimelineWaterfallProps {
  interactions: Interaction[];
  onSelectInteraction: (interaction: Interaction) => void;
  selectedId?: string;
}

export function TimelineWaterfall({
  interactions,
  onSelectInteraction,
  selectedId,
}: TimelineWaterfallProps) {
  const maxLatency = Math.max(...interactions.map((i) => i.latency_ms), 100);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">
            Waterfall Execution Timeline
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Chronological model reasoning latency and tool branch executions
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-indigo-500" /> Model Reasoning
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> Replayed Cache Hit
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-amber-500" /> Tool Execution
          </span>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {interactions.map((step) => {
          const widthPercent = Math.max(
            8,
            Math.min(100, (step.latency_ms / maxLatency) * 100)
          );
          const isSelected = selectedId === step.id;

          return (
            <div
              key={step.id}
              onClick={() => onSelectInteraction(step)}
              className={`cursor-pointer rounded-lg border p-4 transition-all duration-150 ${
                isSelected
                  ? "border-indigo-500 bg-indigo-950/20 shadow-md shadow-indigo-950/50"
                  : "border-zinc-800/80 bg-zinc-950/40 hover:border-zinc-700 hover:bg-zinc-900/60"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono mb-2">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-300">
                    Step #{step.step_index}
                  </span>
                  <span className="font-semibold text-zinc-200">
                    {step.model}
                  </span>
                  <span className="text-zinc-500">({step.provider})</span>
                </div>
                <div className="flex items-center gap-3 text-zinc-400">
                  <span>{step.total_tokens} tokens</span>
                  <span className="flex items-center gap-1 text-zinc-300">
                    <Clock className="h-3 w-3 text-zinc-500" />
                    {step.latency_ms.toFixed(1)}ms
                  </span>
                </div>
              </div>

              {/* Waterfall bar */}
              <div className="w-full h-3 rounded-full bg-zinc-800/60 overflow-hidden flex items-center">
                <div
                  style={{ width: `${widthPercent}%` }}
                  className={`h-full rounded-full transition-all duration-300 ${
                    step.is_cache_hit
                      ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-sm shadow-emerald-500/50"
                      : "bg-gradient-to-r from-indigo-500 to-violet-500 shadow-sm shadow-indigo-500/50"
                  }`}
                />
              </div>

              {/* Tools Executed indicator */}
              {step.tools && step.tools.length > 0 && (
                <div className="mt-2.5 flex items-center gap-2">
                  <Wrench className="h-3 w-3 text-amber-400" />
                  <span className="text-[11px] font-mono text-zinc-400">
                    Tools Executed:{" "}
                    {step.tools.map((t) => t.tool_name).join(", ")}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
