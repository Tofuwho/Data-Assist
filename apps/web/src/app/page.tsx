"use client";

import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Header } from "@/components/Header";
import { AuthCard } from "@/components/AuthCard";
import { ProjectList } from "@/components/ProjectList";
import { CreateWorkspaceModal } from "@/components/CreateWorkspaceModal";
import { CreateProjectModal } from "@/components/CreateProjectModal";
import {
  ShieldCheck,
  History,
  BrainCircuit,
  FileCheck2,
  Loader2,
  FolderPlus,
} from "lucide-react";

export default function Home() {
  const { user, currentWorkspace, loading, refreshWorkspaces } = useAuth();
  const [createWsOpen, setCreateWsOpen] = useState(false);
  const [createProjOpen, setCreateProjOpen] = useState(false);
  const [projectRefreshKey, setProjectRefreshKey] = useState(0);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          <p className="text-xs font-medium text-zinc-400">Loading ClearData workspace...</p>
        </div>
      </div>
    );
  }

  // Not logged in: Show rich landing & AuthCard
  if (!user) {
    return (
      <main className="relative min-h-screen overflow-hidden bg-zinc-950 text-white flex flex-col justify-between">
        {/* Glow Effects */}
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[800px] rounded-full bg-gradient-to-tr from-indigo-600/20 via-violet-600/20 to-purple-600/10 blur-[140px]" />
        <div className="pointer-events-none absolute right-0 bottom-0 h-[400px] w-[600px] rounded-full bg-indigo-900/10 blur-[120px]" />

        {/* Minimal Landing Nav */}
        <nav className="relative z-10 mx-auto flex h-20 w-full max-w-7xl items-center justify-between px-6 lg:px-8">
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/25 ring-1 ring-white/20">
              <span className="font-bold text-white text-base">CD</span>
            </div>
            <span className="text-xl font-bold tracking-tight text-white">ClearData</span>
          </div>
          <div className="flex items-center space-x-2 text-xs font-medium text-zinc-400">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Core MVP Ready</span>
          </div>
        </nav>

        {/* Hero & Auth Card Grid */}
        <div className="relative z-10 mx-auto my-auto max-w-7xl px-6 py-12 lg:px-8">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            {/* Left Column: Mission & Principles */}
            <div className="lg:col-span-7 space-y-8">
              <div className="inline-flex items-center space-x-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">
                <BrainCircuit className="h-3.5 w-3.5" />
                <span>Deterministic Rules + Governed AI</span>
              </div>

              <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl text-white">
                Turn messy company data into{" "}
                <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
                  trusted reports.
                </span>
              </h1>

              <p className="max-w-xl text-base text-zinc-400 leading-relaxed">
                Take ambiguous CSV and Excel uploads, profile anomalies, collaborate with stakeholders, and publish approved reports with full cell-level lineage.
              </p>

              {/* Core Principles Cards */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 pt-2">
                <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4 backdrop-blur-sm">
                  <div className="flex items-center space-x-2.5 text-indigo-400 mb-1.5">
                    <ShieldCheck className="h-4 w-4" />
                    <h2 className="text-xs font-bold uppercase tracking-wider text-white">Immutable Raw Data</h2>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Original files and row entries are never overwritten. Every fix is versioned and reversible.
                  </p>
                </div>

                <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4 backdrop-blur-sm">
                  <div className="flex items-center space-x-2.5 text-violet-400 mb-1.5">
                    <History className="h-4 w-4" />
                    <h2 className="text-xs font-bold uppercase tracking-wider text-white">Auditable Lineage</h2>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Every number in a report traces directly back to source rows and applied rule or human changes.
                  </p>
                </div>

                <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4 backdrop-blur-sm">
                  <div className="flex items-center space-x-2.5 text-emerald-400 mb-1.5">
                    <FileCheck2 className="h-4 w-4" />
                    <h2 className="text-xs font-bold uppercase tracking-wider text-white">Rule Engine First</h2>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Deterministic code transforms what is exact; AI suggestions only target genuine ambiguity.
                  </p>
                </div>

                <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4 backdrop-blur-sm">
                  <div className="flex items-center space-x-2.5 text-purple-400 mb-1.5">
                    <BrainCircuit className="h-4 w-4" />
                    <h2 className="text-xs font-bold uppercase tracking-wider text-white">Human Review Queue</h2>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    AI suggestions below confidence thresholds require human sign-off before applying.
                  </p>
                </div>
              </div>
            </div>

            {/* Right Column: Auth Card */}
            <div className="flex justify-center lg:col-span-5">
              <AuthCard />
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="relative z-10 border-t border-zinc-900 py-6 text-center text-xs text-zinc-400">
          ClearData &copy; 2026. Built with Next.js, FastAPI, Polars, and PostgreSQL.
        </footer>
      </main>
    );
  }

  // Logged In: Show Workspace Shell & Projects
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col">
      <Header onOpenCreateWorkspace={() => setCreateWsOpen(true)} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        {currentWorkspace ? (
          <div className="space-y-8">
            {/* Workspace Banner */}
            <div className="relative overflow-hidden rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900/90 to-zinc-950 p-6 sm:p-8 shadow-xl">
              <div className="absolute right-0 top-0 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl" />
              <div className="relative z-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
                <div>
                  <div className="flex items-center space-x-2.5 mb-2">
                    <span className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
                      Active Workspace
                    </span>
                    <span className="text-xs text-zinc-500">•</span>
                    <span className="text-xs text-zinc-400 capitalize">
                      Your Role: <strong className="text-white">{currentWorkspace.role}</strong>
                    </span>
                  </div>
                  <h2 className="text-2xl sm:text-3xl font-black text-white">{currentWorkspace.name}</h2>
                  <p className="mt-1 text-xs text-zinc-400 max-w-xl">
                    Select a project to inspect datasets, run profiling, and configure cleaning rules.
                  </p>
                </div>

                <div className="flex items-center space-x-3">
                  {(currentWorkspace.role === "admin" || currentWorkspace.role === "steward") && (
                    <button
                      onClick={() => setCreateProjOpen(true)}
                      className="flex items-center space-x-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors"
                    >
                      <FolderPlus className="h-4 w-4" />
                      <span>New Project</span>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Projects Section */}
            <ProjectList
              key={`${currentWorkspace.id}-${projectRefreshKey}`}
              workspace={currentWorkspace}
              onOpenCreateProject={() => setCreateProjOpen(true)}
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-3xl border border-zinc-800 bg-zinc-900/40 p-12 text-center">
            <h2 className="text-xl font-bold text-white">No Workspace Selected</h2>
            <p className="mt-1 text-xs text-zinc-400">
              Create a workspace to start organizing your data cleaning projects.
            </p>
            <button
              onClick={() => setCreateWsOpen(true)}
              className="mt-6 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors"
            >
              Create Workspace
            </button>
          </div>
        )}
      </main>

      {/* Modals */}
      <CreateWorkspaceModal
        isOpen={createWsOpen}
        onClose={() => setCreateWsOpen(false)}
      />

      {currentWorkspace && (
        <CreateProjectModal
          isOpen={createProjOpen}
          workspaceId={currentWorkspace.id}
          onClose={() => setCreateProjOpen(false)}
          onProjectCreated={() => {
            setProjectRefreshKey((k) => k + 1);
            refreshWorkspaces();
          }}
        />
      )}
    </div>
  );
}
