"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Interaction, TestSession } from "@/types/api";
import { StatusBadge, ModeBadge } from "@/components/ui/Badge";
import { TimelineWaterfall } from "@/components/debugger/TimelineWaterfall";
import { InteractionCard } from "@/components/debugger/InteractionCard";

function SessionDetailContent() {
  const params = useParams();
  const sessionId = params.id as string;

  const [session, setSession] = useState<TestSession | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [selectedInteraction, setSelectedInteraction] = useState<Interaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSessionData() {
      try {
        setLoading(true);
        const [sessionData, interactionList] = await Promise.all([
          api.getSession(sessionId),
          api.getInteractions(sessionId),
        ]);
        setSession(sessionData);
        setInteractions(interactionList);
        if (interactionList.length > 0) {
          setSelectedInteraction(interactionList[0]);
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }

    if (sessionId) {
      loadSessionData();
    }
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
        <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
        <span>Loading Waterfall Data...</span>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="rounded-xl border border-rose-800 bg-rose-950/40 p-6 text-rose-300">
        <h3 className="font-semibold text-base mb-1">Session Not Found</h3>
        <p className="text-xs font-mono">{error || "Could not retrieve session"}</p>
        <Link
          href="/sessions"
          className="mt-4 inline-flex items-center gap-2 rounded bg-zinc-800 px-3 py-1.5 text-xs font-mono text-zinc-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Sessions</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Metadata */}
      <div>
        <Link
          href="/sessions"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 mb-3"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Sessions</span>
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-mono text-zinc-100">
              {session.session_name}
            </h1>
            <StatusBadge status={session.status} />
            <ModeBadge mode={session.mode} />
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
            <span>Duration: {session.duration_ms.toFixed(1)}ms</span>
            <span>Tokens: {session.total_tokens.toLocaleString()}</span>
            <span className="text-emerald-400 font-semibold">
              Cost: ${session.total_cost_usd.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      {/* Main Debugger View: Waterfall + Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Waterfall Timeline (Left 5 cols) */}
        <div className="lg:col-span-5">
          <TimelineWaterfall
            interactions={interactions}
            onSelectInteraction={setSelectedInteraction}
            selectedId={selectedInteraction?.id}
          />
        </div>

        {/* Step Inspector (Right 7 cols) */}
        <div className="lg:col-span-7">
          {selectedInteraction ? (
            <InteractionCard interaction={selectedInteraction} />
          ) : (
            <div className="flex h-96 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/30 text-xs font-mono text-zinc-500">
              Select an interaction step from the waterfall to inspect payloads.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SessionDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
          <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
          <span>Loading Waterfall Data...</span>
        </div>
      }
    >
      <SessionDetailContent />
    </Suspense>
  );
}
