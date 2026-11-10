"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { api, Dataset, Project, ReportListItem } from "@/lib/api";
import { Header } from "@/components/Header";
import { AuthCard } from "@/components/AuthCard";
import { CreateWorkspaceModal } from "@/components/CreateWorkspaceModal";
import { UploadDatasetModal } from "@/components/UploadDatasetModal";
import { GenerateReportModal } from "@/components/GenerateReportModal";
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Database,
  FileSpreadsheet,
  FolderKanban,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";

function getCompletenessColor(pct?: number): string {
  if (pct === undefined || pct === null) return "text-zinc-400 bg-zinc-800";
  if (pct >= 95) return "text-emerald-300 bg-emerald-500/15 border-emerald-500/25";
  if (pct >= 80) return "text-amber-300 bg-amber-500/15 border-amber-500/25";
  return "text-rose-300 bg-rose-500/15 border-rose-500/25";
}

function getCompletenessBarColor(pct?: number): string {
  if (pct === undefined || pct === null) return "bg-zinc-600";
  if (pct >= 95) return "bg-emerald-500";
  if (pct >= 80) return "bg-amber-500";
  return "bg-rose-500";
}

export function ProjectWorkspaceClient() {
  const params = useParams<{ projectId: string }>();
  const projectId = params?.projectId || "";
  const router = useRouter();

  const { user, workspaces, currentWorkspace, loading: authLoading } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [createWsOpen, setCreateWsOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [generateReportTarget, setGenerateReportTarget] = useState<{
    open: boolean;
    datasetId?: string;
  }>({ open: false });
  const [deletingReportId, setDeletingReportId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (silent = false) => {
    if (!projectId || !user) return;
    if (!silent) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      const [proj, dsList, repList] = await Promise.all([
        api.getProject(projectId),
        api.listDatasets(projectId),
        api.listProjectReports(projectId).catch(() => [] as ReportListItem[]),
      ]);
      setProject(proj);
      setDatasets(dsList);
      setReports(repList);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load project datasets");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [projectId, user]);

  useEffect(() => {
    if (authLoading || !user || !projectId) return;
    let cancelled = false;

    async function initLoad() {
      try {
        const [proj, dsList, repList] = await Promise.all([
          api.getProject(projectId),
          api.listDatasets(projectId),
          api.listProjectReports(projectId).catch(() => [] as ReportListItem[]),
        ]);
        if (!cancelled) {
          setProject(proj);
          setDatasets(dsList);
          setReports(repList);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load project datasets");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    initLoad();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, projectId]);

  // Poll automatically while any dataset is still processing
  useEffect(() => {
    if (!user || !projectId) return;
    const hasProcessing = datasets.some((d) => d.status === "processing");
    if (!hasProcessing) return;

    const timer = setTimeout(async () => {
      try {
        const fresh = await api.listDatasets(projectId);
        setDatasets(fresh);
      } catch {
        // Keep silent during background polling
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [datasets, projectId, user]);

  const projectWorkspace = useMemo(() => {
    if (!project) return currentWorkspace;
    return workspaces.find((w) => w.id === project.workspace_id) || currentWorkspace;
  }, [project, workspaces, currentWorkspace]);

  const canUpload =
    projectWorkspace?.role === "admin" || projectWorkspace?.role === "steward";
  const isContributor = projectWorkspace?.role === "contributor";

  const handleDeleteReport = async (reportId: string) => {
    if (deletingReportId) return;
    setDeletingReportId(reportId);
    try {
      await api.deleteReport(reportId);
      setReports((prev) => prev.filter((r) => r.id !== reportId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete report");
    } finally {
      setDeletingReportId(null);
    }
  };

  const filteredDatasets = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return datasets;
    return datasets.filter((d) => d.name.toLowerCase().includes(needle));
  }, [datasets, search]);

  const summary = useMemo(() => {
    const readyCount = datasets.filter((d) => d.status === "ready").length;
    const processingCount = datasets.filter((d) => d.status === "processing").length;
    const failedCount = datasets.filter((d) => d.status === "failed").length;
    const openIssues = datasets.reduce(
      (acc, d) => acc + (d.issue_counts?.total ?? 0),
      0
    );
    return { readyCount, processingCount, failedCount, openIssues };
  }, [datasets]);

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          <p className="text-xs font-medium text-zinc-400">Checking session...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 py-12 text-white">
        <div className="mb-6 flex items-center space-x-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/20">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight">ClearData</span>
        </div>
        <AuthCard />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col">
      <Header
        onOpenCreateWorkspace={() => setCreateWsOpen(true)}
        onWorkspaceSelected={() => router.push("/")}
      />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8 space-y-7">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="flex items-center space-x-2 text-xs text-zinc-400">
          <Link
            href="/"
            className="inline-flex items-center space-x-1.5 rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2.5 py-1.5 font-medium text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{projectWorkspace?.name || "Workspaces"}</span>
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
          <span className="inline-flex items-center space-x-1.5 font-semibold text-white">
            <FolderKanban className="h-3.5 w-3.5 text-indigo-400" />
            <span>{project?.name || "Project"}</span>
          </span>
        </nav>

        {/* Error banner */}
        {error && (
          <div className="flex items-center justify-between rounded-2xl border border-rose-500/25 bg-rose-500/10 p-4 text-xs text-rose-300">
            <div className="flex items-center space-x-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => loadData(false)}
              className="inline-flex items-center space-x-1.5 rounded-lg border border-rose-500/30 bg-rose-500/15 px-3 py-1.5 font-semibold text-rose-200 hover:bg-rose-500/25 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* Project Hero Card */}
        <section className="relative overflow-hidden rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900/90 to-zinc-950 p-6 sm:p-8 shadow-xl">
          <div className="pointer-events-none absolute right-0 top-0 h-52 w-52 rounded-full bg-indigo-500/10 blur-3xl" />
          <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
                  Project Workspace
                </span>
                {projectWorkspace && (
                  <span className="text-xs text-zinc-400 capitalize">
                    Role: <strong className="text-white">{projectWorkspace.role}</strong>
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">
                {project?.name || (loading ? "Loading project..." : "Project")}
              </h1>
              <p className="max-w-2xl text-xs text-zinc-400">
                Upload raw CSV, TSV, or Excel datasets to preserve immutable source bytes, run deterministic profiling &amp; issue detection, and explore row-level anomalies.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => loadData(true)}
                disabled={loading || refreshing}
                className="inline-flex items-center space-x-1.5 rounded-xl border border-zinc-800 bg-zinc-900/80 px-3.5 py-2.5 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-indigo-400" : ""}`} />
                <span>Refresh</span>
              </button>

              {canUpload && summary.readyCount > 0 && (
                <button
                  type="button"
                  onClick={() => setGenerateReportTarget({ open: true })}
                  className="inline-flex items-center space-x-2 rounded-xl border border-indigo-500/40 bg-indigo-500/15 px-3.5 py-2.5 text-xs font-semibold text-indigo-200 transition-colors hover:bg-indigo-500/25"
                >
                  <BarChart3 className="h-4 w-4 text-indigo-300" />
                  <span>New Report</span>
                </button>
              )}

              <button
                type="button"
                disabled={!canUpload || loading}
                onClick={() => setUploadOpen(true)}
                title={
                  !canUpload
                    ? "Only Admins and Stewards can upload datasets"
                    : "Upload CSV, TSV, or XLSX dataset"
                }
                className="inline-flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <UploadCloud className="h-4 w-4" />
                <span>Upload Dataset</span>
              </button>
            </div>
          </div>

          {/* Mini Metrics Strip */}
          {!loading && project && (
            <div className="relative z-10 mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-zinc-800/80 pt-5">
              <div className="rounded-xl border border-zinc-800/70 bg-zinc-950/50 px-3.5 py-2.5">
                <p className="text-[11px] font-medium text-zinc-400">Total Datasets</p>
                <p className="mt-0.5 text-lg font-bold text-white">{datasets.length}</p>
              </div>
              <div className="rounded-xl border border-zinc-800/70 bg-zinc-950/50 px-3.5 py-2.5">
                <p className="text-[11px] font-medium text-zinc-400">Ready</p>
                <p className="mt-0.5 text-lg font-bold text-emerald-400">{summary.readyCount}</p>
              </div>
              <div className="rounded-xl border border-zinc-800/70 bg-zinc-950/50 px-3.5 py-2.5">
                <p className="text-[11px] font-medium text-zinc-400">Processing / Failed</p>
                <p className="mt-0.5 text-lg font-bold text-zinc-200">
                  <span className="text-amber-400">{summary.processingCount}</span>
                  <span className="mx-1 text-zinc-600">/</span>
                  <span className="text-rose-400">{summary.failedCount}</span>
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800/70 bg-zinc-950/50 px-3.5 py-2.5">
                <p className="text-[11px] font-medium text-zinc-400">Open Issues</p>
                <p className="mt-0.5 text-lg font-bold text-amber-300">{summary.openIssues}</p>
              </div>
            </div>
          )}
        </section>

        {/* Datasets Toolbar */}
        <section className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center space-x-2.5">
              <h2 className="text-lg font-bold tracking-tight text-white">Datasets</h2>
              <span className="rounded-full border border-zinc-700/60 bg-zinc-800 px-2.5 py-0.5 text-xs font-semibold text-zinc-300">
                {datasets.length}
              </span>
            </div>

            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-zinc-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter datasets..."
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900/60 py-2 pl-10 pr-4 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {loading ? (
            <div className="flex h-64 items-center justify-center rounded-2xl border border-zinc-800/80 bg-zinc-900/30">
              <div className="flex flex-col items-center space-y-3">
                <Loader2 className="h-7 w-7 animate-spin text-indigo-500" />
                <p className="text-xs text-zinc-400">Loading project datasets...</p>
              </div>
            </div>
          ) : filteredDatasets.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/20 p-12 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900 text-zinc-500">
                <Database className="h-7 w-7" />
              </div>
              <h3 className="text-base font-semibold text-white">
                {search ? "No matching datasets" : "No datasets uploaded yet"}
              </h3>
              <p className="mt-1.5 max-w-md text-xs text-zinc-400">
                {search
                  ? "Adjust your search filter or clear it to view all project datasets."
                  : projectWorkspace?.role === "contributor"
                  ? "Datasets appear here once an issue has been assigned to you."
                  : "Upload a CSV, TSV, or Excel workbook to run automatic column profiling and issue detection."}
              </p>
              {!search && canUpload && (
                <button
                  type="button"
                  onClick={() => setUploadOpen(true)}
                  className="mt-5 inline-flex items-center space-x-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors"
                >
                  <UploadCloud className="h-4 w-4" />
                  <span>Upload First Dataset</span>
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3.5">
              {filteredDatasets.map((ds) => {
                const stats = ds.stats_json;
                const counts = ds.issue_counts;
                const completeness = stats?.completeness_pct;

                return (
                  <div
                    key={ds.id}
                    className="group rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 transition-all hover:border-zinc-700 hover:bg-zinc-900/90"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      {/* Left: Title, type, status */}
                      <div className="flex items-start space-x-4 min-w-0">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-indigo-500/20 bg-indigo-500/10 text-indigo-400">
                          <FileSpreadsheet className="h-5 w-5" />
                        </div>
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2.5">
                            <h3 className="truncate text-base font-semibold text-white">
                              {ds.name}
                            </h3>
                            <span className="rounded border border-zinc-700/70 bg-zinc-800/80 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-zinc-300">
                              {ds.source_type}
                            </span>

                            {ds.status === "ready" ? (
                              <span className="inline-flex items-center space-x-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                <span>Ready</span>
                              </span>
                            ) : ds.status === "processing" ? (
                              <span className="inline-flex items-center space-x-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                <span>Processing</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center space-x-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-300">
                                <AlertCircle className="h-3.5 w-3.5" />
                                <span>Failed</span>
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-400">
                            <span>
                              Uploaded {new Date(ds.created_at).toLocaleString()}
                            </span>
                            {stats?.row_count !== undefined && (
                              <span>
                                <strong className="text-zinc-200">
                                  {stats.row_count.toLocaleString()}
                                </strong>{" "}
                                rows
                              </span>
                            )}
                            {stats?.column_count !== undefined && (
                              <span>
                                <strong className="text-zinc-200">{stats.column_count}</strong>{" "}
                                columns
                              </span>
                            )}
                          </div>

                          {ds.status === "failed" && ds.error_message && (
                            <div className="mt-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                              {ds.error_message}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Right: Completeness, Issues, Explore CTA */}
                      <div className="flex flex-wrap items-center gap-4 lg:shrink-0">
                        {/* Completeness */}
                        <div className="min-w-[125px] space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-zinc-400">Completeness</span>
                            <span
                              className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold ${getCompletenessColor(
                                completeness
                              )}`}
                            >
                              {completeness !== undefined ? `${completeness.toFixed(1)}%` : "—"}
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                            <div
                              className={`h-full transition-all ${getCompletenessBarColor(completeness)}`}
                              style={{
                                width: `${
                                  completeness !== undefined
                                    ? Math.min(100, Math.max(0, completeness))
                                    : 0
                                }%`,
                              }}
                            />
                          </div>
                        </div>

                        {/* Issue pills */}
                        <div className="flex items-center gap-1.5">
                          {counts && counts.total > 0 ? (
                            <>
                              {counts.critical > 0 && (
                                <span className="rounded-md border border-rose-500/30 bg-rose-500/15 px-2 py-1 text-[11px] font-semibold text-rose-300">
                                  {counts.critical} Critical
                                </span>
                              )}
                              {counts.high > 0 && (
                                <span className="rounded-md border border-orange-500/30 bg-orange-500/15 px-2 py-1 text-[11px] font-semibold text-orange-300">
                                  {counts.high} High
                                </span>
                              )}
                              {counts.medium > 0 && (
                                <span className="rounded-md border border-amber-500/30 bg-amber-500/15 px-2 py-1 text-[11px] font-semibold text-amber-300">
                                  {counts.medium} Med
                                </span>
                              )}
                              {counts.low > 0 && (
                                <span className="rounded-md border border-sky-500/30 bg-sky-500/15 px-2 py-1 text-[11px] font-semibold text-sky-300">
                                  {counts.low} Low
                                </span>
                              )}
                            </>
                          ) : ds.status === "ready" ? (
                            <span className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300">
                              0 Issues
                            </span>
                          ) : null}
                        </div>

                        {ds.status === "ready" ? (
                          <div className="flex items-center gap-2">
                            {canUpload && (
                              <button
                                type="button"
                                onClick={() =>
                                  setGenerateReportTarget({ open: true, datasetId: ds.id })
                                }
                                className="inline-flex items-center space-x-1.5 rounded-xl border border-indigo-500/35 bg-indigo-500/15 px-3 py-2 text-xs font-semibold text-indigo-200 transition-colors hover:bg-indigo-500/25"
                              >
                                <BarChart3 className="h-3.5 w-3.5" />
                                <span>Analyze</span>
                              </button>
                            )}
                            <Link
                              href={`/projects/${projectId}/datasets/${ds.id}`}
                              className="inline-flex items-center space-x-1.5 rounded-xl bg-zinc-800 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-indigo-600"
                            >
                              <span>Explore Dataset</span>
                              <ChevronRight className="h-3.5 w-3.5" />
                            </Link>
                          </div>
                        ) : (
                          <span className="inline-flex cursor-not-allowed items-center space-x-1.5 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-500">
                            <span>{ds.status === "processing" ? "Processing..." : "Unavailable"}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Stakeholder Reports Section */}
        {!loading && !isContributor && (
          <section className="space-y-4 pt-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-2.5">
                <h2 className="text-lg font-bold tracking-tight text-white">
                  Stakeholder Reports
                </h2>
                <span className="rounded-full border border-zinc-700/60 bg-zinc-800 px-2.5 py-0.5 text-xs font-semibold text-zinc-300">
                  {reports.length}
                </span>
              </div>

              {canUpload && summary.readyCount > 0 && (
                <button
                  type="button"
                  onClick={() => setGenerateReportTarget({ open: true })}
                  className="inline-flex items-center space-x-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Generate Stakeholder Report</span>
                </button>
              )}
            </div>

            {reports.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/20 p-8 text-center">
                <p className="text-sm font-semibold text-zinc-300">
                  No stakeholder reports generated yet
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Turn any ready dataset into KPI cards, interactive charts, executive narrative, and traceable row lineage.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
                {reports.map((rep) => (
                  <div
                    key={rep.id}
                    className="flex flex-col justify-between rounded-2xl border border-zinc-800/80 bg-zinc-900/50 p-5 transition-all hover:border-zinc-700 hover:bg-zinc-900/90"
                  >
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-indigo-500/30 bg-indigo-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-300">
                            {rep.status.replaceAll("_", " ")}
                          </span>
                          <span className="rounded border border-zinc-700/70 bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-300">
                            {rep.dataset_name} · v{rep.version_number}
                          </span>
                        </div>
                        <span className="text-[11px] text-zinc-500 capitalize">
                          {rep.template.replaceAll("_", " ")}
                        </span>
                      </div>

                      <h3 className="text-base font-bold text-white">{rep.title}</h3>
                      <p className="text-xs text-zinc-400">
                        {rep.block_count} report block(s) · Updated{" "}
                        {new Date(rep.updated_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-zinc-800/80 pt-3">
                      <Link
                        href={`/projects/${projectId}/reports/${rep.id}`}
                        className="inline-flex items-center space-x-1.5 rounded-xl bg-zinc-800 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-600 transition-colors"
                      >
                        <BarChart3 className="h-3.5 w-3.5" />
                        <span>Open Report</span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </Link>

                      {canUpload && (
                        <button
                          type="button"
                          onClick={() => handleDeleteReport(rep.id)}
                          disabled={deletingReportId === rep.id}
                          aria-label={`Delete report ${rep.title}`}
                          className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1.5 text-zinc-500 hover:border-rose-500/30 hover:text-rose-400 disabled:opacity-40"
                        >
                          {deletingReportId === rep.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      <CreateWorkspaceModal
        isOpen={createWsOpen}
        onClose={() => setCreateWsOpen(false)}
      />

      <UploadDatasetModal
        isOpen={uploadOpen}
        projectId={projectId}
        onClose={() => setUploadOpen(false)}
        onUploadCompleted={(freshDatasets) => {
          setDatasets(freshDatasets);
        }}
      />

      {generateReportTarget.open && (
        <GenerateReportModal
          key={generateReportTarget.datasetId || "default-ds"}
          datasets={datasets}
          initialDatasetId={generateReportTarget.datasetId}
          onCreated={(created) => {
            setGenerateReportTarget({ open: false });
            router.push(`/projects/${projectId}/reports/${created.id}`);
          }}
          onClose={() => setGenerateReportTarget({ open: false })}
        />
      )}
    </div>
  );
}
