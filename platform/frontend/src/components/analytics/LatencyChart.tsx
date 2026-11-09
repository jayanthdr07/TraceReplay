"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface LatencyData {
  provider: string;
  liveMs: number;
  replayMs: number;
}

interface LatencyChartProps {
  data: LatencyData[];
}

export function LatencyChart({ data }: LatencyChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/30 text-xs text-zinc-500 font-mono">
        No latency data recorded yet.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-lg">
      <div className="mb-4">
        <h4 className="text-sm font-semibold text-zinc-200">
          Live vs. Replay Latency Comparison (ms)
        </h4>
        <p className="text-xs text-zinc-400 mt-0.5">
          Near-zero millisecond playback speeds enabled by local fixture caching
        </p>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis dataKey="provider" stroke="#71717a" fontSize={11} fontStyle="mono" />
            <YAxis stroke="#71717a" fontSize={11} fontStyle="mono" />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                borderColor: "#3f3f46",
                borderRadius: "8px",
                fontSize: "12px",
                fontFamily: "monospace",
              }}
            />
            <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
            <Bar dataKey="liveMs" name="Live Provider (ms)" fill="#6366f1" radius={[4, 4, 0, 0]} />
            <Bar dataKey="replayMs" name="TraceReplay (ms)" fill="#10b981" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
