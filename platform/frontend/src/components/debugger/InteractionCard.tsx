import React from "react";
import { Interaction } from "@/types/api";
import { JsonViewer } from "@/components/ui/JsonViewer";

export function InteractionCard({ interaction }: { interaction: Interaction }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-6 space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
        <div>
          <span className="font-mono text-xs uppercase text-indigo-400 font-semibold tracking-wider">
            Interaction Step #{interaction.step_index}
          </span>
          <h3 className="text-xl font-bold text-zinc-100 font-mono mt-0.5">
            {interaction.model}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {interaction.is_cache_hit && (
            <span className="rounded-full bg-emerald-950 border border-emerald-800 text-emerald-300 px-3 py-1 font-mono text-xs">
              ⚡ REPLAY CACHE HIT
            </span>
          )}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
          <span className="text-[10px] uppercase font-mono text-zinc-500">Latency</span>
          <p className="font-mono text-lg font-semibold text-zinc-200 mt-1">
            {interaction.latency_ms.toFixed(1)}ms
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
          <span className="text-[10px] uppercase font-mono text-zinc-500">Prompt Tokens</span>
          <p className="font-mono text-lg font-semibold text-zinc-200 mt-1">
            {interaction.prompt_tokens}
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
          <span className="text-[10px] uppercase font-mono text-zinc-500">Completion Tokens</span>
          <p className="font-mono text-lg font-semibold text-zinc-200 mt-1">
            {interaction.completion_tokens}
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
          <span className="text-[10px] uppercase font-mono text-zinc-500">Cost (USD)</span>
          <p className="font-mono text-lg font-semibold text-emerald-400 mt-1">
            ${interaction.cost_usd.toFixed(6)}
          </p>
        </div>
      </div>

      {/* Request and Response JSON Viewers */}
      <div className="space-y-4">
        <JsonViewer
          title="Input Messages & Model Parameters"
          data={interaction.request_payload}
        />
        <JsonViewer
          title="Model Output & Response Payload"
          data={interaction.response_payload}
        />
      </div>
    </div>
  );
}
