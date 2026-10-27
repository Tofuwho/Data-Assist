"use client";

import React, { useEffect, useState } from "react";
import { api, Project, Workspace } from "@/lib/api";
import {
  FolderKanban,
  Plus,
  Search,
  Calendar,
  ChevronRight,
  Database,
  Loader2,
  FileSpreadsheet,
} from "lucide-react";

interface ProjectListProps {
  workspace: Workspace;
  onOpenCreateProject: () => void;
  onSelectProject?: (project: Project) => void;
}

export function ProjectList({
  workspace,
  onOpenCreateProject,
  onSelectProject,
}: ProjectListProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const data = await api.getProjects(workspace.id);
        if (isMounted) {
          setProjects(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (isMounted) {
          if (err instanceof Error) {
            setError(err.message);
          } else {
            setError("Failed to load projects");
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      isMounted = false;
    };
  }, [workspace.id]);

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  const canCreate = workspace.role === "admin" || workspace.role === "steward";

  return (
    <div className="space-y-6">
      {/* Header section with title and New Project action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <span>Projects</span>
            <span className="rounded-full bg-zinc-800 border border-zinc-700/60 px-2.5 py-0.5 text-xs font-semibold text-zinc-300">
              {projects.length}
            </span>
          </h1>
          <p className="mt-1 text-xs text-zinc-400">
            Workspaces contain projects where you upload raw messy datasets, clean them, and build reports.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={onOpenCreateProject}
            disabled={!canCreate}
            title={!canCreate ? "Only Admins and Stewards can create projects" : ""}
            className="flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 transition-all hover:opacity-95 hover:shadow-indigo-600/30 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3.5 top-3 h-4 w-4 text-zinc-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter projects by name..."
          className="w-full rounded-xl border border-zinc-800 bg-zinc-900/60 py-2.5 pl-10 pr-4 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-400">
          {error}
        </div>
      )}

      {/* Content State */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/20 p-12 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 border border-zinc-800 text-zinc-500 mb-4">
            <FolderKanban className="h-7 w-7" />
          </div>
          <h3 className="text-base font-semibold text-white">
            {search ? "No matching projects" : "No projects yet in this workspace"}
          </h3>
          <p className="mt-1.5 max-w-sm text-xs text-zinc-400">
            {search
              ? "Try adjusting your search filter or clear the input."
              : "Create a project to start uploading CSV or Excel files, run profiling, and fix data inconsistencies."}
          </p>
          {!search && canCreate && (
            <button
              onClick={onOpenCreateProject}
              className="mt-5 flex items-center space-x-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Create First Project</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((project) => (
            <div
              key={project.id}
              onClick={() => onSelectProject && onSelectProject(project)}
              className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 transition-all hover:border-zinc-700 hover:bg-zinc-900/90 hover:shadow-xl hover:shadow-black/40 cursor-pointer"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 group-hover:scale-105 transition-transform">
                    <Database className="h-5 w-5" />
                  </div>
                  <span className="flex items-center space-x-1 text-[11px] font-medium text-zinc-400">
                    <Calendar className="h-3.5 w-3.5" />
                    <span>{new Date(project.created_at).toLocaleDateString()}</span>
                  </span>
                </div>

                <div className="mt-4">
                  <h3 className="text-base font-semibold text-white group-hover:text-indigo-300 transition-colors">
                    {project.name}
                  </h3>
                  <p className="mt-1 text-xs text-zinc-400 line-clamp-2">
                    Managed data cleaning pipeline & verified reporting.
                  </p>
                </div>
              </div>

              <div className="mt-6 border-t border-zinc-800/70 pt-4 flex items-center justify-between">
                <div className="flex items-center space-x-2 text-[11px] font-medium text-zinc-400">
                  <FileSpreadsheet className="h-3.5 w-3.5 text-zinc-500" />
                  <span>Phase 1 Ingestion Ready</span>
                </div>
                <div className="flex items-center space-x-1 text-xs font-semibold text-indigo-400 group-hover:translate-x-0.5 transition-transform">
                  <span>Open</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
