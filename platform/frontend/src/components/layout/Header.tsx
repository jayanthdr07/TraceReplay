"use client";

import React, { useEffect, useState } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { HealthResponse } from "@/types/api";

export function Header() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getHealth();
      setHealth(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    api
      .getHealth()
      .then((res) => {
        if (!ignore) {
          setHealth(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError((err as Error).message);
          setLoading(false);
        }
      });

    const interval = setInterval(() => {
      api
        .getHealth()
        .then((res) => setHealth(res))
        .catch((err) => setError((err as Error).message));
    }, 30000); // 30s live health polling

    return () => {
      ignore = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="h-16 border-b border-zinc-800/80 bg-zinc-950/60 px-6 backdrop-blur-md flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm text-zinc-400">Environment:</span>
        <span className="rounded bg-zinc-800 px-2.5 py-1 text-xs font-mono font-medium text-zinc-200 uppercase">
          {health?.environment || "Development"}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Live Database Pill */}
        {error ? (
          <div className="flex items-center gap-1.5 rounded-full border border-rose-800/80 bg-rose-950/60 px-3 py-1 text-xs font-mono text-rose-300">
            <AlertCircle className="h-3.5 w-3.5 text-rose-400" />
            <span>Backend Offline</span>
          </div>
        ) : health ? (
          <div className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/80 px-3.5 py-1 text-xs font-mono">
            <span
              className={`h-2 w-2 rounded-full ${
                health.database.status === "connected" || health.database.status === "healthy"
                  ? "bg-emerald-400 shadow-sm shadow-emerald-400/50"
                  : "bg-amber-400"
              }`}
            />
            <span className="text-zinc-300">
              {health.database.mode === "cloud"
                ? "Cloud Mode (Supabase Connected)"
                : "Local Mode (Filesystem)"}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-xs text-zinc-500 font-mono">
            <RefreshCw className="h-3 w-3 animate-spin" />
            <span>Connecting...</span>
          </div>
        )}

        <button
          onClick={fetchHealth}
          disabled={loading}
          className="rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200 transition-colors"
          title="Refresh connection status"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
    </header>
  );
}
