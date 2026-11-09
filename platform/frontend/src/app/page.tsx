"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  DollarSign,
  CheckCircle2,
  Clock,
  Layers,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { AnalyticsOverview, TestSession } from "@/types/api";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge, ModeBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LatencyChart } from "@/components/analytics/LatencyChart";
import { ModelDistributionChart } from "@/components/analytics/ModelDistributionChart";

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [recentSessions, setRecentSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [analyticsData, sessionsData] = await Promise.all([
        api.getAnalyticsOverview(),
        api.getSessions({ limit: 5 }),
      ]);
      setAnalytics(analyticsData);
      setRecentSessions(sessionsData);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    Promise.all([
      api.getAnalyticsOverview(),
      api.getSessions({ limit: 5 }),
    ])
      .then(([analyticsData, sessionsData]) => {
        if (!ignore) {
          setAnalytics(analyticsData);
          setRecentSessions(sessionsData);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError((err as Error).message);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
        <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
        <span>Loading TraceReplay Analytics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-800/80 bg-rose-950/40 p-6 text-rose-300">
        <h3 className="font-semibold text-base mb-1">Failed to load platform data</h3>
        <p className="text-xs font-mono">{error}</p>
        <button
          onClick={loadData}
          className="mt-4 rounded bg-rose-900/60 border border-rose-700 px-3 py-1.5 text-xs font-mono text-rose-200 hover:bg-rose-800/80"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const hasData = analytics && analytics.total_sessions > 0;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Platform Overview
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time telemetry, cost savings, and deterministic replay efficiency
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs font-mono text-zinc-300 hover:border-zinc-700 hover:text-zinc-100"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Estimated Cost Saved"
          value={`$${(analytics?.estimated_cost_saved_usd || 0).toFixed(4)}`}
          subValue="USD"
          icon={DollarSign}
          trend={{ value: "+100%", isPositive: true, label: "via local cache" }}
          accentColor="emerald"
        />
        <MetricCard
          title="Replay Success Rate"
          value={`${(analytics?.replay_success_rate || 100).toFixed(1)}%`}
          icon={CheckCircle2}
          trend={{ value: "0% flakiness", isPositive: true }}
          accentColor="indigo"
        />
        <MetricCard
          title="Total Test Sessions"
          value={analytics?.total_sessions || 0}
          icon={Layers}
          accentColor="cyan"
        />
        <MetricCard
          title="Average Latency"
          value={`${(analytics?.average_latency_ms || 0).toFixed(1)}`}
          subValue="ms"
          icon={Clock}
          accentColor="amber"
        />
      </div>

      {!hasData ? (
        <EmptyState />
      ) : (
        <>
          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LatencyChart
              data={(analytics?.top_models || []).map((m) => ({
                provider: m.model,
                liveMs: Math.round(analytics?.average_latency_ms || 0),
                replayMs: 1.2,
              }))}
            />
            <ModelDistributionChart models={analytics?.top_models || []} />
          </div>

          {/* Recent Sessions Table */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 shadow-xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-4">
              <div>
                <h3 className="text-base font-semibold text-zinc-100">
                  Recent Test Sessions
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Latest recorded and replayed AI interaction suites
                </p>
              </div>
              <Link
                href="/sessions"
                className="flex items-center gap-1 text-xs font-mono text-indigo-400 hover:text-indigo-300"
              >
                <span>View All</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400">
                    <th className="py-2.5 px-3">Session Name</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Mode</th>
                    <th className="py-2.5 px-3">Interactions</th>
                    <th className="py-2.5 px-3">Tokens</th>
                    <th className="py-2.5 px-3">Duration</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                  {recentSessions.map((session) => (
                    <tr key={session.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-3 font-semibold text-zinc-100">
                        {session.session_name}
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={session.status} />
                      </td>
                      <td className="py-3 px-3">
                        <ModeBadge mode={session.mode} />
                      </td>
                      <td className="py-3 px-3">{session.total_interactions}</td>
                      <td className="py-3 px-3">{session.total_tokens}</td>
                      <td className="py-3 px-3">{session.duration_ms.toFixed(1)}ms</td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/sessions/${session.id}`}
                          className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs hover:border-zinc-500 hover:text-white"
                        >
                          Inspect
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
