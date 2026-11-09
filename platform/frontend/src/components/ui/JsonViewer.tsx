"use client";

import React, { useState } from "react";
import { Check, Copy, Eye, EyeOff } from "lucide-react";

interface JsonViewerProps {
  data: unknown;
  title?: string;
  defaultExpanded?: boolean;
}

export function JsonViewer({
  data,
  title,
  defaultExpanded = true,
}: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);

  const formattedJson = JSON.stringify(data, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formattedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/80 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-zinc-800/80 px-3.5 py-2">
        <div className="flex items-center gap-2">
          {title && (
            <span className="font-semibold text-zinc-300">{title}</span>
          )}
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
            {typeof data === "object" && data !== null
              ? `${Array.isArray(data) ? data.length : Object.keys(data).length} items`
              : typeof data}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 rounded px-2 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
            title={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? (
              <EyeOff className="h-3.5 w-3.5" />
            ) : (
              <Eye className="h-3.5 w-3.5" />
            )}
            <span>{expanded ? "Collapse" : "Expand"}</span>
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded px-2 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="max-h-96 overflow-y-auto p-3.5">
          <pre className="text-zinc-300 leading-relaxed overflow-x-auto whitespace-pre-wrap">
            {formattedJson}
          </pre>
        </div>
      )}
    </div>
  );
}
