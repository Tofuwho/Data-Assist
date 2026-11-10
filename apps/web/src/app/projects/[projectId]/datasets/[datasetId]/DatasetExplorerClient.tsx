"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  api,
  Dataset,
  DatasetColumn,
  DatasetIssue,
  Project,
  RowItem,
} from "@/lib/api";
import { Header } from "@/components/Header";
import { AuthCard } from "@/components/AuthCard";
import { CreateWorkspaceModal } from "@/components/CreateWorkspaceModal";
import { DatasetGrid } from "@/components/DatasetGrid";
import { IssuesPanel } from "@/components/IssuesPanel";
import { ColumnProfileSidebar } from "@/components/ColumnProfileSidebar";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Columns3,
  FileSpreadsheet,
  FolderKanban,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";

export function DatasetExplorerClient() {
  const params = useParams<{ projectId: string; datasetId: string }>();
  const projectId = params?.projectId || "";
  const datasetId = params?.datasetId || "";
  const router = useRouter();

  const { user, workspaces, currentWorkspace, loading: authLoading } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [issues, setIssues] = useState<DatasetIssue[]>([]);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState<string | null>(null);

  // Grid query & pagination state
  const [rows, setRows] = useState<RowItem[]>([]);
  const [rowsLoading, setRowsLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const [searchInput, setSearchInput] = useState("");
  const [debouncedFilter, setDebouncedFilter] = useState("");
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [activeIssue, setActiveIssue] = useState<DatasetIssue | null>(null);

  // Panels & modals
  const [issuesOpen, setIssuesOpen] = useState(true);
  const [selectedColumnId, setSelectedColumnId] = useState<string | null>(null);
  const [createWsOpen, setCreateWsOpen] = useState(false);
  const [reprofiling, setReprofiling] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);

  // Debounce search filter
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilter(searchInput.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Load dataset metadata, columns, and issues
  useEffect(() => {
    if (authLoading || !user || !projectId || !datasetId) return;
    let cancelled = false;

    async function loadMeta() {
      try {
        const [proj, ds, cols, issList] = await Promise.all([
          api.getProject(projectId),
          api.getDataset(datasetId),
          api.getDatasetColumns(datasetId),
          api.getDatasetIssues(datasetId),
        ]);
        if (!cancelled) {
          setProject(proj);
          setDataset(ds);
          setColumns(cols);
          setIssues(issList);
          setMetaError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setMetaError(err instanceof Error ? err.message : "Failed to load dataset profile");
        }
      } finally {
        if (!cancelled) {
          setMetaLoading(false);
        }
      }
    }

    loadMeta();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, projectId, datasetId, reloadNonce]);

  // Load first page of rows whenever query filters change
  useEffect(() => {
    if (authLoading || !user || !datasetId) return;
    let cancelled = false;

    async function loadFirstPage() {
      try {
        const page = await api.getDatasetRows(datasetId, {
          limit: 100,
          sort: sortCol || undefined,
          sort_dir: sortCol ? sortDir : undefined,
          filter: debouncedFilter || undefined,
          issue_id: activeIssue?.id || undefined,
        });
        if (!cancelled) {
          setRows(page.items);
          setTotalCount(page.total_count);
          setNextCursor(page.next_cursor);
          setHasMore(page.has_more);
          setRowsError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setRowsError(err instanceof Error ? err.message : "Failed to load dataset rows");
        }
      } finally {
        if (!cancelled) {
          setRowsLoading(false);
          setLoadingMore(false);
        }
      }
    }

    loadFirstPage();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user, datasetId, sortCol, sortDir, debouncedFilter, activeIssue, reloadNonce]);

  const handleLoadMore = useCallback(async () => {
    if (!hasMore || !nextCursor || loadingMore || rowsLoading || !datasetId) return;
    setLoadingMore(true);
    try {
      const page = await api.getDatasetRows(datasetId, {
        cursor: nextCursor,
        limit: 100,
        sort: sortCol || undefined,
        sort_dir: sortCol ? sortDir : undefined,
        filter: debouncedFilter || undefined,
        issue_id: activeIssue?.id || undefined,
      });
      setRows((prev) => [...prev, ...page.items]);
      setTotalCount(page.total_count);
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      setRowsError(null);
    } catch (err: unknown) {
      setRowsError(err instanceof Error ? err.message : "Failed to load next rows page");
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, nextCursor, loadingMore, rowsLoading, datasetId, sortCol, sortDir, debouncedFilter, activeIssue]);

  const projectWorkspace = useMemo(() => {
    if (!project) return currentWorkspace;
    return workspaces.find((w) => w.id === project.workspace_id) || currentWorkspace;
  }, [project, workspaces, currentWorkspace]);

  const canManage =
    projectWorkspace?.role === "admin" || projectWorkspace?.role === "steward";

  const selectedColumn = useMemo(
    () => columns.find((c) => c.id === selectedColumnId) || null,
    [columns, selectedColumnId]
  );

  const issueCounts = useMemo(() => {
    if (dataset?.issue_counts) return dataset.issue_counts;
    const c = { total: issues.length, critical: 0, high: 0, medium: 0, low: 0 };
    issues.forEach((i) => {
      if (i.severity === "critical") c.critical += 1;
      else if (i.severity === "high") c.high += 1;
      else if (i.severity === "medium") c.medium += 1;
      else if (i.severity === "low") c.low += 1;
    });
    return c;
  }, [dataset, issues]);

  const handleToggleSort = (colName: string) => {
    setRowsLoading(true);
    if (sortCol !== colName) {
      setSortCol(colName);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol(null);
      setSortDir("asc");
    }
  };

  const handleSelectIssue = (issue: DatasetIssue | null) => {
    setRowsLoading(true);
    setActiveIssue(issue);
    if (issue?.column_id) {
      setSelectedColumnId(issue.column_id);
    }
  };

  const handleReprofile = async () => {
    if (!datasetId || reprofiling) return;
    setReprofiling(true);
    try {
      const job = await api.reprofileDataset(datasetId);
      // Poll briefly if queued on async worker
      if (job.status !== "finished" && job.status !== "failed") {
        for (let i = 0; i < 30; i += 1) {
          await new Promise((r) => setTimeout(r, 800));
          const latest = await api.getJobStatus(job.job_id);
          if (latest.status === "finished" || latest.status === "failed") {
            break;
          }
        }
      }
      setMetaLoading(true);
      setRowsLoading(true);
      setReloadNonce((n) => n + 1);
    } catch (err: unknown) {
      setMetaError(err instanceof Error ? err.message : "Failed to re-profile dataset");
    } finally {
      setReprofiling(false);
    }
  };

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

  const rowCountStat = dataset?.stats_json?.row_count ?? totalCount;
  const colCountStat = dataset?.stats_json?.column_count ?? columns.length;
  const completeness = dataset?.stats_json?.completeness_pct;

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-white">
      <Header
        onOpenCreateWorkspace={() => setCreateWsOpen(true)}
        onWorkspaceSelected={() => router.push("/")}
      />

      {/* Top Breadcrumb + Summary Strip */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="mx-auto max-w-[1680px] px-4 py-3.5 sm:px-6 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Breadcrumb */}
            <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
              <Link
                href={`/projects/${projectId}`}
                className="inline-flex items-center space-x-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1 font-medium text-zinc-300 hover:border-zinc-700 hover:text-white transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Back to Project</span>
              </Link>
              <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
              <Link
                href={`/projects/${projectId}`}
                className="inline-flex items-center space-x-1 hover:text-white transition-colors"
              >
                <FolderKanban className="h-3.5 w-3.5 text-indigo-400" />
                <span>{project?.name || "Project"}</span>
              </Link>
              <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
              <span className="inline-flex items-center space-x-1.5 font-semibold text-white">
                <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />
                <span>{dataset?.name || (metaLoading ? "Loading dataset..." : "Dataset")}</span>
              </span>
            </nav>

            {/* Right Actions */}
            <div className="flex flex-wrap items-center gap-2">
              {canManage && (
                <button
                  type="button"
                  onClick={handleReprofile}
                  disabled={reprofiling || metaLoading}
                  className="inline-flex items-center space-x-1.5 rounded-xl border border-zinc-700/80 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-zinc-600 hover:text-white transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${reprofiling ? "animate-spin text-indigo-400" : ""}`} />
                  <span>{reprofiling ? "Profiling..." : "Re-profile"}</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setIssuesOpen((prev) => !prev)}
                className={`inline-flex items-center space-x-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  issuesOpen
                    ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-200"
                    : "border-zinc-700/80 bg-zinc-900 text-zinc-300 hover:text-white"
                }`}
              >
                {issuesOpen ? (
                  <PanelLeftClose className="h-3.5 w-3.5" />
                ) : (
                  <PanelLeftOpen className="h-3.5 w-3.5" />
                )}
                <span>Issues ({issues.length})</span>
              </button>
            </div>
          </div>

          {metaError && (
            <div className="flex items-center space-x-2 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{metaError}</span>
            </div>
          )}

          {/* Summary Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-800/80 bg-zinc-950/70 px-4 py-2.5">
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <div>
                <span className="text-zinc-500">Rows: </span>
                <strong className="font-mono text-white">{rowCountStat.toLocaleString()}</strong>
              </div>
              <div className="h-3.5 w-[1px] bg-zinc-800" />
              <div>
                <span className="text-zinc-500">Columns: </span>
                <strong className="font-mono text-white">{colCountStat}</strong>
              </div>
              <div className="h-3.5 w-[1px] bg-zinc-800" />
              <div className="flex items-center space-x-1.5">
                <span className="text-zinc-500">Completeness: </span>
                <strong
                  className={`font-mono ${
                    completeness === undefined
                      ? "text-zinc-400"
                      : completeness >= 95
                      ? "text-emerald-400"
                      : completeness >= 80
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}
                >
                  {completeness !== undefined ? `${completeness.toFixed(1)}%` : "—"}
                </strong>
              </div>
              <div className="h-3.5 w-[1px] bg-zinc-800" />
              <div className="flex flex-wrap items-center gap-1.5">
                {issueCounts.total === 0 ? (
                  <span className="inline-flex items-center space-x-1 rounded-md border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Clean Dataset</span>
                  </span>
                ) : (
                  <>
                    {issueCounts.critical > 0 && (
                      <span className="rounded-md border border-rose-500/30 bg-rose-500/15 px-2 py-0.5 text-[11px] font-semibold text-rose-300">
                        {issueCounts.critical} Critical
                      </span>
                    )}
                    {issueCounts.high > 0 && (
                      <span className="rounded-md border border-orange-500/30 bg-orange-500/15 px-2 py-0.5 text-[11px] font-semibold text-orange-300">
                        {issueCounts.high} High
                      </span>
                    )}
                    {issueCounts.medium > 0 && (
                      <span className="rounded-md border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                        {issueCounts.medium} Medium
                      </span>
                    )}
                    {issueCounts.low > 0 && (
                      <span className="rounded-md border border-sky-500/30 bg-sky-500/15 px-2 py-0.5 text-[11px] font-semibold text-sky-300">
                        {issueCounts.low} Low
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Quick Column Selector + Search */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-2 h-3.5 w-3.5 text-zinc-500" />
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => {
                    setRowsLoading(true);
                    setSearchInput(e.target.value);
                  }}
                  placeholder="Search cells..."
                  className="w-48 sm:w-60 rounded-xl border border-zinc-800 bg-zinc-900 py-1.5 pl-8 pr-7 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                />
                {searchInput && (
                  <button
                    type="button"
                    onClick={() => {
                      setRowsLoading(true);
                      setSearchInput("");
                      setDebouncedFilter("");
                    }}
                    className="absolute right-2 top-2 text-zinc-400 hover:text-white"
                    aria-label="Clear search"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              <div className="inline-flex items-center space-x-1 rounded-xl border border-zinc-800 bg-zinc-900 px-2 py-1">
                <Columns3 className="h-3.5 w-3.5 text-indigo-400" />
                <select
                  aria-label="Inspect column profile"
                  value={selectedColumnId || ""}
                  onChange={(e) => setSelectedColumnId(e.target.value || null)}
                  className="bg-transparent text-xs text-zinc-200 focus:outline-none"
                >
                  <option value="" className="bg-zinc-900">
                    Column profile...
                  </option>
                  {columns.map((c) => (
                    <option key={c.id} value={c.id} className="bg-zinc-900">
                      {c.name} ({c.inferred_type || "raw"})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Active Issue Focus Banner */}
          {activeIssue && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-indigo-500/35 bg-indigo-500/12 px-4 py-2 text-xs">
              <div className="flex items-center space-x-2 text-indigo-200">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                <span>
                  <strong className="uppercase">{activeIssue.type.replaceAll("_", " ")}</strong>:{" "}
                  {activeIssue.description} ({activeIssue.affected_count} affected rows)
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleSelectIssue(null)}
                className="inline-flex items-center space-x-1 rounded-lg bg-indigo-600/30 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-indigo-600/50 transition-colors"
              >
                <X className="h-3 w-3" />
                <span>Show all rows</span>
              </button>
            </div>
          )}

          {sortCol && !activeIssue && (
            <div className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900/70 px-3.5 py-1.5 text-[11px] text-zinc-300">
              <span>
                Sorted by <strong className="text-white">{sortCol}</strong> ({sortDir})
              </span>
              <button
                type="button"
                onClick={() => {
                  setRowsLoading(true);
                  setSortCol(null);
                }}
                className="text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Clear sort
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main 3-Pane Explorer Workspace */}
      <div className="mx-auto flex w-full max-w-[1680px] flex-1 flex-col lg:flex-row overflow-hidden min-h-[560px]">
        {issuesOpen && (
          <div className="max-h-[340px] lg:max-h-none lg:h-[calc(100vh-210px)] flex">
            <IssuesPanel
              issues={issues}
              columns={columns}
              activeIssueId={activeIssue?.id || null}
              loading={metaLoading}
              error={metaError}
              onSelectIssue={handleSelectIssue}
              onInspectColumn={(colId) => setSelectedColumnId(colId)}
              onClose={() => setIssuesOpen(false)}
            />
          </div>
        )}

        <div className="flex flex-1 min-w-0 flex-col lg:h-[calc(100vh-210px)]">
          {!selectedColumn && columns.length > 0 && (
            <div className="flex items-center justify-between border-b border-zinc-800/70 bg-zinc-950 px-4 py-1.5 text-[11px] text-zinc-400">
              <span className="inline-flex items-center space-x-1.5">
                <BarChart3 className="h-3.5 w-3.5 text-indigo-400" />
                <span>Tip: Click any column header to inspect type inference, distributions, and format patterns.</span>
              </span>
            </div>
          )}

          <DatasetGrid
            columns={columns}
            rows={rows}
            issues={issues}
            activeIssue={activeIssue}
            selectedColumnId={selectedColumnId}
            sortCol={sortCol}
            sortDir={sortDir}
            totalCount={totalCount}
            hasMore={hasMore}
            loading={rowsLoading}
            loadingMore={loadingMore}
            error={rowsError}
            onSelectColumn={(col) =>
              setSelectedColumnId((prev) => (prev === col.id ? null : col.id))
            }
            onToggleSort={handleToggleSort}
            onLoadMore={handleLoadMore}
            onRetry={() => {
              setRowsLoading(true);
              setReloadNonce((n) => n + 1);
            }}
          />
        </div>

        {selectedColumn && (
          <div className="max-h-[420px] lg:max-h-none lg:h-[calc(100vh-210px)] flex">
            <ColumnProfileSidebar
              column={selectedColumn}
              issues={issues}
              loading={metaLoading}
              onClose={() => setSelectedColumnId(null)}
              onSelectIssue={handleSelectIssue}
            />
          </div>
        )}
      </div>

      <CreateWorkspaceModal
        isOpen={createWsOpen}
        onClose={() => setCreateWsOpen(false)}
      />
    </div>
  );
}
