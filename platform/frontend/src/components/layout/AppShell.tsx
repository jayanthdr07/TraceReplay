import React, { Suspense } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100 font-sans antialiased">
      <Suspense fallback={<aside className="w-64 flex-shrink-0 border-r border-zinc-800/80 bg-zinc-950/80" />}>
        <Sidebar />
      </Suspense>
      <div className="flex flex-1 flex-col overflow-hidden">
        <Suspense fallback={<header className="h-16 border-b border-zinc-800/80 bg-zinc-950/60" />}>
          <Header />
        </Suspense>
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </div>
  );
}
