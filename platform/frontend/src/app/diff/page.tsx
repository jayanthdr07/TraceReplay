"use client";

import React, { Suspense, useEffect, useState } from "react";
import { GitCompare, Sliders, RefreshCw, FileText, CheckCircle2, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { TestSession } from "@/types/api";
import { SemanticDiffViewer } from "@/components/diff/SemanticDiffViewer";

function calculateSimilarity(str1: string, str2: string): number {
  if (str1 === str2) return 1.0;
  if (!str1.length || !str2.length) return 0.0;

  const words1 = str1.trim().toLowerCase().split(/\s+/);
  const words2 = str2.trim().toLowerCase().split(/\s+/);
  const set1 = new Set(words1);
  const set2 = new Set(words2);

  let intersection = 0;
  for (const word of set1) {
    if (set2.has(word)) intersection++;
  }

  const union = new Set([...words1, ...words2]).size;
  return union === 0 ? 1.0 : intersection / union;
}

function DiffContent() {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [threshold, setThreshold] = useState<number>(0.85);

  const [expectedText, setExpectedText] = useState<string>(
    JSON.stringify(
      {
        status: "success",
        model: "gemini-1.5-pro",
        result: {
          intent: "customer_support",
          sentiment: "positive",
          suggested_response: "Thank you for reaching out! We have processed your order #9421 and it is in transit.",
        },
      },
      null,
      2
    )
  );

  const [actualText, setActualText] = useState<string>(
    JSON.stringify(
      {
        status: "success",
        model: "gemini-1.5-pro",
        result: {
          intent: "customer_support",
          sentiment: "neutral",
          suggested_response: "Thanks for reaching out! Your order #9421 is confirmed and currently in transit.",
        },
      },
      null,
      2
    )
  );

  useEffect(() => {
    let ignore = false;
    api
      .getSessions({ limit: 10 })
      .then((data) => {
        if (!ignore) {
          setSessions(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to load sessions for diff:", err);
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const similarityScore = calculateSimilarity(expectedText, actualText);
  const isPassing = similarityScore >= threshold;

  const handleSelectSession = (sessionId: string) => {
    setSelectedSessionId(sessionId);
    const session = sessions.find((s) => s.id === sessionId);
    if (session) {
      setExpectedText(
        JSON.stringify(
          {
            session_name: session.session_name,
            mode: session.mode,
            status: session.status,
            total_tokens: session.total_tokens,
            expected_behavior: "Deterministic baseline recorded by TraceReplay SDK",
            metadata: session.metadata,
          },
          null,
          2
        )
      );
      setActualText(
        JSON.stringify(
          {
            session_name: session.session_name,
            mode: "replay",
            status: session.status,
            total_tokens: session.total_tokens,
            replayed_result: "Cache hit from local fixture storage",
            metadata: session.metadata,
          },
          null,
          2
        )
      );
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <GitCompare className="h-4 w-4" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
              Semantic Diff Inspector
            </h1>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Compare expected baseline fixtures against live replayed outputs with threshold-based drift detection
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Similarity score pill */}
          <div
            className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 font-mono text-xs font-semibold ${
              isPassing
                ? "border-emerald-800 bg-emerald-950/70 text-emerald-300"
                : "border-rose-800 bg-rose-950/70 text-rose-300"
            }`}
          >
            {isPassing ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-rose-400" />
            )}
            <span>{(similarityScore * 100).toFixed(1)}% Match</span>
            <span className="text-[10px] text-zinc-400 font-normal">
              ({isPassing ? "PASSED" : "DIVERGED"})
            </span>
          </div>
        </div>
      </div>

      {/* Control Panel: Session Picker & Threshold Slider */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
        {/* Load From Session */}
        <div className="md:col-span-7 flex flex-col justify-center">
          <label className="block text-xs font-mono text-zinc-400 mb-1.5 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-indigo-400" />
            <span>Load Data from Recorded Test Session</span>
          </label>
          <select
            value={selectedSessionId}
            onChange={(e) => handleSelectSession(e.target.value)}
            disabled={loading}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-200 focus:border-indigo-500 focus:outline-none"
          >
            <option value="">-- Choose a session or edit text manually below --</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_name} ({s.mode} - {s.status})
              </option>
            ))}
          </select>
        </div>

        {/* Threshold Slider */}
        <div className="md:col-span-5 flex flex-col justify-center">
          <div className="flex items-center justify-between text-xs font-mono mb-1.5">
            <span className="text-zinc-400 flex items-center gap-1.5">
              <Sliders className="h-3.5 w-3.5 text-indigo-400" />
              <span>Similarity Threshold:</span>
            </span>
            <span className="font-semibold text-zinc-200">
              {(threshold * 100).toFixed(0)}%
            </span>
          </div>
          <input
            type="range"
            min="0.50"
            max="1.00"
            step="0.01"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-full accent-indigo-500 cursor-pointer"
          />
        </div>
      </div>

      {/* Editable Inputs Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Expected Input */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800 mb-3">
            <span className="font-mono text-xs font-semibold text-zinc-300">
              Recorded Baseline Fixture (Expected)
            </span>
            <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-mono text-zinc-400">
              JSON / Text
            </span>
          </div>
          <textarea
            value={expectedText}
            onChange={(e) => setExpectedText(e.target.value)}
            rows={10}
            className="w-full rounded-lg border border-zinc-800/80 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 leading-relaxed focus:border-indigo-500 focus:outline-none"
            placeholder="Paste expected baseline output..."
          />
        </div>

        {/* Actual Input */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800 mb-3">
            <span className="font-mono text-xs font-semibold text-zinc-300">
              Replayed Response (Actual)
            </span>
            <span className="rounded bg-indigo-950 text-indigo-300 border border-indigo-800/80 px-2 py-0.5 text-[10px] font-mono">
              JSON / Text
            </span>
          </div>
          <textarea
            value={actualText}
            onChange={(e) => setActualText(e.target.value)}
            rows={10}
            className="w-full rounded-lg border border-zinc-800/80 bg-zinc-950 p-3 font-mono text-xs text-zinc-200 leading-relaxed focus:border-indigo-500 focus:outline-none"
            placeholder="Paste actual replayed output..."
          />
        </div>
      </div>

      {/* Side-by-Side Visual Diff Inspector */}
      <SemanticDiffViewer
        expectedText={expectedText}
        actualText={actualText}
        similarityScore={similarityScore}
        threshold={threshold}
      />
    </div>
  );
}

export default function DiffPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
          <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
          <span>Loading Semantic Diff Inspector...</span>
        </div>
      }
    >
      <DiffContent />
    </Suspense>
  );
}

