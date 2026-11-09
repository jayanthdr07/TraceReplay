"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  Activity,
  BarChart3,
  Boxes,
  Database,
  GitCompare,
  Layers,
} from "lucide-react";

const navigationItems = [
  { name: "Overview", href: "/", icon: BarChart3 },
  { name: "Sessions", href: "/sessions", icon: Layers },
  { name: "Projects", href: "/projects", icon: Boxes },
  { name: "Diff Inspector", href: "/diff", icon: GitCompare },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex-shrink-0 border-r border-zinc-800/80 bg-zinc-950/80 flex flex-col justify-between p-4">
      <div>
        {/* Brand Header */}
        <Link href="/" className="flex items-center gap-2.5 px-2 py-3 mb-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-lg shadow-indigo-500/25">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <span className="font-mono text-base font-bold tracking-tight text-zinc-100">
              TraceReplay
            </span>
            <span className="block text-[10px] uppercase font-mono tracking-wider text-indigo-400">
              Web Platform
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="space-y-1">
          {navigationItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.name}
                href={item.href}
                className={clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-indigo-600/15 text-indigo-300 font-semibold border border-indigo-500/30"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                )}
              >
                <item.icon
                  className={clsx(
                    "h-4 w-4",
                    isActive ? "text-indigo-400" : "text-zinc-400"
                  )}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3 text-xs">
        <div className="flex items-center gap-2 text-zinc-400">
          <Database className="h-3.5 w-3.5 text-emerald-400" />
          <span className="font-mono">API: v0.1.0</span>
        </div>
        <p className="mt-1.5 text-[11px] text-zinc-500">
          FastAPI + Supabase PostgreSQL
        </p>
      </div>
    </aside>
  );
}
