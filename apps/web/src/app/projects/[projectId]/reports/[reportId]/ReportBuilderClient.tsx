"use client";

import React, { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  api,
  Project,
  ReportBlockDefinition,
  ReportDetail,
  ReportLayout,
  ReportStatus,
} from "@/lib/api";
import { Header } from "@/components/Header";
import { AuthCard } from "@/components/AuthCard";
import { CreateWorkspaceModal } from "@/components/CreateWorkspaceModal";
import { ReportBlockCard } from "@/components/ReportBlockCard";
import { BlockEditorModal } from "@/components/BlockEditorModal";
import { LineageDrawer } from "@/components/LineageDrawer";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  Edit3,
  Eye,
  FileSpreadsheet,
  FolderKanban,
  Loader2,
  PlusCircle,
  Printer,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

function statusBadgeStyle(status: string): string {
  switch (status) {
    case "published":
      return "border-emerald-500/35 bg-emerald-500/15 text-emerald-300 print:border-emerald-700 print:text-emerald-800 print:bg-emerald-50";
    case "approved":
      return "border-indigo-500/35 bg-indigo-500/15 text-indigo-300 print:border-indigo-700 print:text-indigo-800 print:bg-indigo-50";
    case "in_review":
      return "border-amber-500/35 bg-amber-500/15 text-amber-300 print:border-amber-700 print:text-amber-800 print:bg-amber-50";
    default:
      return "border-zinc-700 bg-zinc-800 text-zinc-300 print:border-slate-400 print:text-slate-700 print:bg-slate-100";
  }
}

export function ReportBuilderClient() {
  const params = useParams<{ projectId: string; reportId: string }>();
  const projectId = params?.projectId || "";
  const reportId = params?.reportId || "";
  const router = useRouter();

  const { user, workspaces, currentWorkspace, loading: authLoading } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [regeneratingNarrative, setRegeneratingNarrative] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Presentation vs Edit mode (`null` auto-picks based on user role without useEffect setState)
  const [presentationPref, setPresentationPref] = useState<boolean | null>(null);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [createWsOpen, setCreateWsOpen] = useState(false);

  // Add/edit block modal state
  const [blockEditorState, setBlockEditorState] = useState<{
    open: boolean;
    block: ReportBlockDefinition | null;
  }>({ open: false, block: null });

  // Lineage inspector state
  const [lineageTarget, setLineageTarget] = useState<{
    blockId: string;
    blockTitle: string;
    bucketKey: string | null;
    bucketLabel: string | null;
  } | null>(null);

  useEffect(() => {
    if (authLoading || !user || !projectId || !reportId) return;
    let cancelled = false;

    async function initLoad() {
      try {
        const [proj, rep] = await Promise.all([
          api.getProject(projectId),
          api.getReport(reportId),
        ]);
        if (!cancelled) {
          setProject(proj);
          setReport(rep);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load stakeholder report");
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
  }, [authLoading, user, projectId, reportId]);

  const projectWorkspace = useMemo(() => {
    if (!project) return currentWorkspace;
    return workspaces.find((w) => w.id === project.workspace_id) || currentWorkspace;
  }, [project, workspaces, currentWorkspace]);

  const canEdit =
    projectWorkspace?.role === "admin" || projectWorkspace?.role === "steward";
  const isPresentationMode =
    presentationPref ?? (projectWorkspace?.role === "stakeholder");

  const saveLayout = async (nextLayout: ReportLayout) => {
    if (!report || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateReport(report.id, { layout_json: nextLayout });
      setReport(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save report layout");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTitle = async () => {
    if (!report || editingTitle === null) return;
    const trimmed = editingTitle.trim();
    if (!trimmed || trimmed === report.title) {
      setEditingTitle(null);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateReport(report.id, { title: trimmed });
      setReport(updated);
      setEditingTitle(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to rename report");
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (nextStatus: ReportStatus) => {
    if (!report || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateReport(report.id, { status: nextStatus });
      setReport(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update report status");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveBlock = async (blockDef: ReportBlockDefinition) => {
    if (!report) return;
    const blocks = [...(report.layout_json?.blocks || [])];
    const existingIdx = blocks.findIndex((b) => b.id === blockDef.id);
    if (existingIdx >= 0) {
      blocks[existingIdx] = blockDef;
    } else {
      blocks.push(blockDef);
    }
    setBlockEditorState({ open: false, block: null });
    await saveLayout({
      ...(report.layout_json || { version: 1, template: report.template }),
      blocks,
    });
  };

  const handleDeleteBlock = async (blockId: string) => {
    if (!report) return;
    const blocks = (report.layout_json?.blocks || []).filter((b) => b.id !== blockId);
    await saveLayout({
      ...(report.layout_json || { version: 1, template: report.template }),
      blocks,
    });
  };

  const handleMoveBlock = async (index: number, delta: number) => {
    if (!report) return;
    const blocks = [...(report.layout_json?.blocks || [])];
    const targetIdx = index + delta;
    if (targetIdx < 0 || targetIdx >= blocks.length) return;
    const [moved] = blocks.splice(index, 1);
    blocks.splice(targetIdx, 0, moved);
    await saveLayout({
      ...(report.layout_json || { version: 1, template: report.template }),
      blocks,
    });
  };

  const handleRegenerateNarrative = async () => {
    if (!report || regeneratingNarrative) return;
    setRegeneratingNarrative(true);
    setError(null);
    try {
      const updated = await api.generateReportNarrative(report.id);
      setReport(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to synthesize narrative");
    } finally {
      setRegeneratingNarrative(false);
    }
  };

  const handleRecompute = async () => {
    if (!report || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.computeReport(report.id);
      setReport(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to recompute report");
    } finally {
      setSaving(false);
    }
  };

  const handleExportXlsx = async () => {
    if (!report || exporting) return;
    setExporting(true);
    setError(null);
    try {
      await api.exportReportWorkbook(report.id, report.title);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to export Excel workbook");
    } finally {
      setExporting(false);
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

  const layoutBlocks = report?.layout_json?.blocks || [];
  const overview = report?.analysis?.overview;

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-white print:bg-white print:text-slate-900">
      <div className="print:hidden">
        <Header
          onOpenCreateWorkspace={() => setCreateWsOpen(true)}
          onWorkspaceSelected={() => router.push("/")}
        />
      </div>

      {/* Top Navigation & Action Toolbar */}
      <div className="border-b border-zinc-800 bg-zinc-900/60 print:hidden">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <Link
              href={`/projects/${projectId}`}
              className="inline-flex items-center space-x-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1 font-medium text-zinc-300 hover:border-zinc-700 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Project</span>
            </Link>
            <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
            <Link
              href={`/projects/${projectId}`}
              className="inline-flex items-center space-x-1 hover:text-white transition-colors"
            >
              <FolderKanban className="h-3.5 w-3.5 text-indigo-400" />
              <span>{project?.name || "Project"}</span>
            </Link>
            {report && (
              <>
                <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
                <Link
                  href={`/projects/${projectId}/datasets/${report.dataset_id}`}
                  className="inline-flex items-center space-x-1 hover:text-white transition-colors"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />
                  <span>{report.dataset_name}</span>
                </Link>
              </>
            )}
          </nav>

          {report && (
            <div className="flex flex-wrap items-center gap-2">
              {canEdit && (
                <button
                  type="button"
                  onClick={() => setPresentationPref(!isPresentationMode)}
                  className={`inline-flex items-center space-x-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors ${
                    isPresentationMode
                      ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-200"
                      : "border-zinc-700/80 bg-zinc-900 text-zinc-200 hover:border-zinc-600"
                  }`}
                >
                  {isPresentationMode ? (
                    <>
                      <Edit3 className="h-3.5 w-3.5" />
                      <span>Switch to Builder</span>
                    </>
                  ) : (
                    <>
                      <Eye className="h-3.5 w-3.5" />
                      <span>Presentation View</span>
                    </>
                  )}
                </button>
              )}

              {canEdit && !isPresentationMode && (
                <>
                  <button
                    type="button"
                    onClick={() => setBlockEditorState({ open: true, block: null })}
                    className="inline-flex items-center space-x-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                  >
                    <PlusCircle className="h-3.5 w-3.5" />
                    <span>Add Block</span>
                  </button>

                  <select
                    aria-label="Report workflow status"
                    value={report.status}
                    disabled={saving}
                    onChange={(e) => handleStatusChange(e.target.value as ReportStatus)}
                    className="rounded-xl border border-zinc-700/80 bg-zinc-900 px-2.5 py-1.5 text-xs font-semibold text-zinc-200 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="draft">Draft</option>
                    <option value="in_review">In Review</option>
                    <option value="approved">Approved</option>
                    <option value="published">Published</option>
                  </select>
                </>
              )}

              <button
                type="button"
                onClick={handleRecompute}
                disabled={saving}
                title="Recompute metrics from locked dataset version"
                className="inline-flex items-center space-x-1.5 rounded-xl border border-zinc-700/80 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-zinc-600 hover:text-white disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${saving ? "animate-spin text-indigo-400" : ""}`} />
                <span className="hidden sm:inline">Refresh</span>
              </button>

              <button
                type="button"
                onClick={handleExportXlsx}
                disabled={exporting}
                className="inline-flex items-center space-x-1.5 rounded-xl border border-emerald-500/35 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50"
              >
                {exporting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                <span>Export XLSX</span>
              </button>

              <button
                type="button"
                onClick={() => window.print()}
                className="inline-flex items-center space-x-1.5 rounded-xl border border-zinc-700/80 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-zinc-600 hover:text-white"
              >
                <Printer className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Print / PDF</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-7 sm:px-6 lg:px-8 space-y-6 print:px-0 print:py-2">
        {error && (
          <div className="flex items-center space-x-2 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 print:hidden">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex h-80 flex-col items-center justify-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
            <p className="text-xs text-zinc-400">Evaluating report metrics &amp; quality checks...</p>
          </div>
        ) : !report ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-10 text-center text-sm text-zinc-400">
            Report not found or inaccessible.
          </div>
        ) : (
          <>
            {/* Executive Cover Banner */}
            <header className="rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-zinc-950 p-6 sm:p-7 shadow-xl print:rounded-xl print:border-slate-300 print:bg-white print:bg-none print:shadow-none print:p-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusBadgeStyle(
                        report.status
                      )}`}
                    >
                      {report.status.replaceAll("_", " ")}
                    </span>
                    <span className="rounded-md border border-zinc-700/70 bg-zinc-800/80 px-2 py-0.5 text-[11px] font-mono text-zinc-300 print:border-slate-300 print:bg-slate-100 print:text-slate-700">
                      Source: {report.dataset_name} · v{report.version_number}
                    </span>
                    <span className="rounded-md border border-indigo-500/25 bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium capitalize text-indigo-300 print:border-indigo-300 print:bg-indigo-50 print:text-indigo-800">
                      {report.template.replaceAll("_", " ")}
                    </span>
                  </div>

                  {editingTitle !== null && canEdit && !isPresentationMode ? (
                    <div className="flex items-center space-x-2 max-w-2xl">
                      <input
                        type="text"
                        autoFocus
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveTitle();
                          if (e.key === "Escape") setEditingTitle(null);
                        }}
                        className="w-full rounded-xl border border-indigo-500 bg-zinc-950 px-3 py-1.5 text-xl font-bold text-white focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={handleSaveTitle}
                        className="inline-flex items-center space-x-1 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                      >
                        <Check className="h-3.5 w-3.5" />
                        <span>Save</span>
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2.5">
                      <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white print:text-slate-950">
                        {report.title}
                      </h1>
                      {canEdit && !isPresentationMode && (
                        <button
                          type="button"
                          onClick={() => setEditingTitle(report.title)}
                          title="Rename report"
                          className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white print:hidden"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  )}

                  <p className="text-xs text-zinc-400 print:text-slate-600">
                    Click any KPI value, bar segment, donut slice, chart point, or summary row to trace exact underlying dataset records &amp; version audit history.
                  </p>
                </div>

                {overview && (
                  <div className="flex flex-wrap items-center gap-3 shrink-0 rounded-2xl border border-zinc-800/80 bg-zinc-950/60 px-4 py-3 text-xs print:border-slate-300 print:bg-slate-50">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-zinc-500">Rows</p>
                      <p className="font-mono text-sm font-bold text-white print:text-slate-900">
                        {overview.row_count.toLocaleString()}
                      </p>
                    </div>
                    <div className="h-6 w-[1px] bg-zinc-800 print:bg-slate-300" />
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-zinc-500">Completeness</p>
                      <p className="font-mono text-sm font-bold text-emerald-400 print:text-emerald-700">
                        {overview.completeness_pct}%
                      </p>
                    </div>
                    <div className="h-6 w-[1px] bg-zinc-800 print:bg-slate-300" />
                    <div className="flex items-center space-x-1.5">
                      {overview.readiness === "verified" ? (
                        <ShieldCheck className="h-4 w-4 text-emerald-400 print:text-emerald-700" />
                      ) : (
                        <ShieldAlert className="h-4 w-4 text-amber-400 print:text-amber-700" />
                      )}
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-zinc-500">Readiness</p>
                        <p className="font-semibold capitalize text-zinc-200 print:text-slate-900">
                          {overview.readiness.replaceAll("_", " ")} ({overview.readiness_score})
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </header>

            {/* Report Canvas Grid */}
            {report.computed_blocks.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 p-12 text-center">
                <p className="text-sm font-semibold text-zinc-300">No report blocks added yet</p>
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => setBlockEditorState({ open: true, block: null })}
                    className="mt-4 inline-flex items-center space-x-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                  >
                    <PlusCircle className="h-4 w-4" />
                    <span>Add First Block</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
                {report.computed_blocks.map((block, idx) => {
                  const defBlock = layoutBlocks.find((b) => b.id === block.id) || {
                    id: block.id,
                    type: block.type,
                    title: block.title,
                    subtitle: block.subtitle,
                    width: block.width,
                    config: block.config,
                  };
                  return (
                    <ReportBlockCard
                      key={block.id}
                      block={block}
                      index={idx}
                      totalBlocks={report.computed_blocks.length}
                      presentationMode={isPresentationMode}
                      canEdit={canEdit}
                      regeneratingNarrative={regeneratingNarrative}
                      onInspectLineage={(blockId, blockTitle, bucketKey, bucketLabel) =>
                        setLineageTarget({ blockId, blockTitle, bucketKey, bucketLabel })
                      }
                      onEdit={() => setBlockEditorState({ open: true, block: defBlock })}
                      onDelete={() => handleDeleteBlock(block.id)}
                      onMoveUp={() => handleMoveBlock(idx, -1)}
                      onMoveDown={() => handleMoveBlock(idx, 1)}
                      onRegenerateNarrative={handleRegenerateNarrative}
                    />
                  );
                })}
              </div>
            )}

            <footer className="border-t border-zinc-800/80 pt-4 text-center text-[11px] text-zinc-500 print:border-slate-300 print:text-slate-600">
              ClearData · Immutable raw source traceability · Metrics locked to{" "}
              <span className="font-mono">{report.dataset_name}</span> v{report.version_number}
            </footer>
          </>
        )}
      </main>

      <CreateWorkspaceModal
        isOpen={createWsOpen}
        onClose={() => setCreateWsOpen(false)}
      />

      {blockEditorState.open && report && (
        <BlockEditorModal
          key={blockEditorState.block?.id || "new-block"}
          existingBlock={blockEditorState.block}
          analysis={report.analysis}
          onSave={handleSaveBlock}
          onClose={() => setBlockEditorState({ open: false, block: null })}
        />
      )}

      {lineageTarget && report && (
        <LineageDrawer
          key={`${lineageTarget.blockId}:${lineageTarget.bucketKey ?? "all"}`}
          reportId={report.id}
          projectId={projectId}
          blockId={lineageTarget.blockId}
          blockTitle={lineageTarget.blockTitle}
          bucketKey={lineageTarget.bucketKey}
          bucketLabel={lineageTarget.bucketLabel}
          onSelectExcluded={() =>
            setLineageTarget((prev) =>
              prev
                ? {
                    ...prev,
                    bucketKey: "__excluded__",
                    bucketLabel: "Excluded / Unparseable Records",
                  }
                : null
            )
          }
          onClose={() => setLineageTarget(null)}
        />
      )}
    </div>
  );
}
