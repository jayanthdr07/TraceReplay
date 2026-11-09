"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Search, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { SessionMode, SessionStatus, TestSession } from "@/types/api";
import { StatusBadge, ModeBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<SessionStatus | "">("");
  const [modeFilter, setModeFilter] = useState<SessionMode | "">("");

  const loadSessions = async () => {
    try {
      setLoading(true);
      const data = await api.getSessions({
        mode: modeFilter || undefined,
      });
      setSessions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    api
      .getSessions({
        mode: modeFilter || undefined,
      })
      .then((data) => {
        if (!ignore) {
          setSessions(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error(err);
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [statusFilter, modeFilter]);

  const filteredSessions = sessions.filter(
    (s) =>
      (!statusFilter || s.status === statusFilter) &&
      s.session_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Sessions Explorer
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Search, filter, and inspect recorded AI session runs
          </p>
        </div>
        <button
          onClick={loadSessions}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs font-mono text-zinc-300 hover:border-zinc-700"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search sessions by name..."
            className="w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-9 pr-3 py-2 text-xs font-mono text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as SessionStatus | "")}
          className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-300 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="passed">Passed</option>
          <option value="failed">Failed</option>
          <option value="recorded">Recorded</option>
        </select>

        {/* Mode Filter */}
        <select
          value={modeFilter}
          onChange={(e) => setModeFilter(e.target.value as SessionMode | "")}
          className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-300 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All Modes</option>
          <option value="replay">Replay</option>
          <option value="record">Record</option>
          <option value="auto">Auto</option>
          <option value="passthrough">Passthrough</option>
        </select>
      </div>

      {/* Sessions Table */}
      {loading ? (
        <div className="flex h-64 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
          <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
          <span>Loading Sessions...</span>
        </div>
      ) : filteredSessions.length === 0 ? (
        <EmptyState title="No matching sessions found" />
      ) : (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 shadow-xl overflow-hidden">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-zinc-950/80 border-b border-zinc-800 text-zinc-400">
              <tr>
                <th className="py-3 px-4">Session Name</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4">Interactions</th>
                <th className="py-3 px-4">Tokens</th>
                <th className="py-3 px-4">Cost Saved</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {filteredSessions.map((session) => (
                <tr key={session.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-zinc-100">
                    {session.session_name}
                  </td>
                  <td className="py-3.5 px-4">
                    <StatusBadge status={session.status} />
                  </td>
                  <td className="py-3.5 px-4">
                    <ModeBadge mode={session.mode} />
                  </td>
                  <td className="py-3.5 px-4">{session.total_interactions}</td>
                  <td className="py-3.5 px-4">{session.total_tokens.toLocaleString()}</td>
                  <td className="py-3.5 px-4 text-emerald-400">
                    ${session.total_cost_usd.toFixed(4)}
                  </td>
                  <td className="py-3.5 px-4">{session.duration_ms.toFixed(1)}ms</td>
                  <td className="py-3.5 px-4 text-right">
                    <Link
                      href={`/sessions/${session.id}`}
                      className="rounded border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs hover:border-zinc-500 hover:text-white"
                    >
                      Inspect Waterfall
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
