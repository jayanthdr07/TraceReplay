"use client";

import React, { useEffect, useState } from "react";
import { Plus, Database, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { HealthResponse, Project } from "@/types/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // New Project Form State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectSlug, setProjectSlug] = useState("");
  const [projectDesc, setProjectDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const [projList, healthRes] = await Promise.all([
        api.getProjects(),
        api.getHealth(),
      ]);
      setProjects(projList);
      setHealth(healthRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    Promise.all([api.getProjects(), api.getHealth()])
      .then(([projList, healthRes]) => {
        if (!ignore) {
          setProjects(projList);
          setHealth(healthRes);
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
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName || !projectSlug) return;

    try {
      setCreating(true);
      await api.createProject({
        name: projectName,
        slug: projectSlug,
        description: projectDesc,
      });
      setIsModalOpen(false);
      setProjectName("");
      setProjectSlug("");
      setProjectDesc("");
      loadData();
    } catch (err) {
      alert(`Error creating project: ${(err as Error).message}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Projects & Infrastructure
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Scoped AI testing environments and live database connection health
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span>New Project</span>
        </button>
      </div>

      {/* Database Diagnostic Status */}
      {health && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-lg">
          <h3 className="text-sm font-semibold text-zinc-200 mb-4 flex items-center gap-2">
            <Database className="h-4 w-4 text-emerald-400" />
            <span>Database & Storage Diagnostics</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
              <span className="text-zinc-500">Engine Mode:</span>
              <p className="text-zinc-200 font-semibold mt-1 uppercase">
                {health.database.mode} Mode
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
              <span className="text-zinc-500">Provider:</span>
              <p className="text-emerald-400 font-semibold mt-1">
                {health.database.provider}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
              <span className="text-zinc-500">Connection Status:</span>
              <p className="text-emerald-400 font-semibold mt-1 uppercase flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                {health.database.status}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Projects Grid */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-zinc-100">Active Projects</h3>
        {loading ? (
          <div className="flex h-32 items-center justify-center font-mono text-xs text-zinc-400 gap-2">
            <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
            <span>Loading Projects...</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-900/30 p-8 text-center text-xs font-mono text-zinc-500">
            No projects found. Click &quot;New Project&quot; above to create your first workspace.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((proj) => (
              <div
                key={proj.id}
                className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-zinc-100 text-sm">{proj.name}</h4>
                  <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-mono text-zinc-400">
                    {proj.slug}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 line-clamp-2">
                  {proj.description || "No description provided."}
                </p>
                <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] font-mono text-zinc-500">
                  <span>ID: {proj.id.substring(0, 8)}...</span>
                  <span>{new Date(proj.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Project Modal Dialog */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-zinc-100">Create New Project</h3>
            <p className="text-xs text-zinc-400 mt-1">
              Add a new scoped testing project to your organization.
            </p>

            <form onSubmit={handleCreate} className="mt-5 space-y-4 font-mono text-xs">
              <div>
                <label className="block text-zinc-300 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  value={projectName}
                  onChange={(e) => {
                    setProjectName(e.target.value);
                    if (!projectSlug) {
                      setProjectSlug(
                        e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "-")
                      );
                    }
                  }}
                  placeholder="e.g. Support Agent"
                  className="w-full rounded border border-zinc-800 bg-zinc-900 p-2.5 text-zinc-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-zinc-300 mb-1">Slug</label>
                <input
                  type="text"
                  required
                  value={projectSlug}
                  onChange={(e) => setProjectSlug(e.target.value)}
                  placeholder="e.g. support-agent"
                  className="w-full rounded border border-zinc-800 bg-zinc-900 p-2.5 text-zinc-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-zinc-300 mb-1">Description (Optional)</label>
                <textarea
                  value={projectDesc}
                  onChange={(e) => setProjectDesc(e.target.value)}
                  placeholder="Project scope and details..."
                  rows={3}
                  className="w-full rounded border border-zinc-800 bg-zinc-900 p-2.5 text-zinc-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded bg-indigo-600 px-4 py-1.5 text-white hover:bg-indigo-500 font-semibold"
                >
                  {creating ? "Creating..." : "Save Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
