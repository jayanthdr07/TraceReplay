"use client";

import React from "react";
import { ModelUsageStat } from "@/types/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function ModelDistributionChart({ models }: { models: ModelUsageStat[] }) {
  if (!models || models.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/30 text-xs text-zinc-500 font-mono">
        No model interactions registered yet.
      </div>
    );
  }

  const chartData = models.map((m) => ({
    name: m.model,
    tokens: m.total_tokens,
    cost: `$${m.total_cost_usd.toFixed(4)}`,
  }));

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-lg">
      <div className="mb-4">
        <h4 className="text-sm font-semibold text-zinc-200">
          Token Consumption by AI Model
        </h4>
        <p className="text-xs text-zinc-400 mt-0.5">
          Distribution of recorded tokens across distinct LLM architectures
        </p>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis dataKey="name" stroke="#71717a" fontSize={11} fontStyle="mono" />
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
            <Bar dataKey="tokens" name="Total Tokens" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
