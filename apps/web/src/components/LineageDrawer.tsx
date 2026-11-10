"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api, BlockLineageResponse, LineageRowItem } from "@/lib/api";
import {
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  History,
  Layers,
  Loader2,
  Table2,
  X,
} from "lucide-react";

interface LineageDrawerProps {
  reportId: string;
  projectId: string;
  blockId: string;
  blockTitle?: string;
  bucketKey: string | null;
  bucketLabel?: string | null;
  onSelectExcluded?: () => void;
  onClose: () => void;
}

export function LineageDrawer({
  reportId,
  projectId,
  blockId,
  blockTitle,
  bucketKey,
  bucketLabel,
  onSelectExcluded,
  onClose,
}: LineageDrawerProps) {
  const [data, setData] = useState<BlockLineageResponse | null>(null);
  const [rows, setRows] = useState<LineageRowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchLineage() {
      try {
        const res = await api.getBlockLineage(reportId, blockId, {
          bucket_key: bucketKey ?? undefined,
          limit: 50,
          offset: 0,
        });
        if (!cancelled) {
          setData(res);
          setRows(res.rows);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load source row lineage");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchLineage();
    return () => {
      cancelled = true;
    };
  }, [reportId, blockId, bucketKey]);

  const handleLoadMore = async () => {
    if (!data || !data.has_more || loadingMore) return;
    setLoadingMore(true);
    try {
      const next = await api.getBlockLineage(reportId, blockId, {
        bucket_key: bucketKey ?? undefined,
        limit: 50,
        offset: rows.length,
      });
      setData(next);
      setRows((prev) => [...prev, ...next.rows]);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load next rows");
    } finally {
      setLoadingMore(false);
    }
  };

  // Order highlight columns first so analysts immediately inspect relevant metric/dimension fields
  const orderedColumns = React.useMemo(() => {
    if (!data) return [];
    const highlights = data.highlight_columns || [];
    const rest = data.columns.filter((c) => !highlights.includes(c));
    return [...highlights.filter((c) => data.columns.includes(c)), ...rest];
  }, [data]);

  const highlightSet = React.useMemo(
    () => new Set(data?.highlight_columns || []),
    [data]
  );

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-xs">
      <div
        className="flex h-full w-full max-w-4xl flex-col border-l border-zinc-800 bg-zinc-950 text-white shadow-2xl"
        role="dialog"
        aria-label="Row Lineage Inspector"
      >
        {/* Top Header */}
        <div className="flex items-start justify-between border-b border-zinc-800 bg-zinc-900/70 px-6 py-4">
          <div className="min-w-0 space-y-1 pr-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center space-x-1.5 rounded-md border border-indigo-500/30 bg-indigo-500/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-300">
                <Layers className="h-3 w-3" />
                <span>Source Row Lineage</span>
              </span>
              {data && (
                <span className="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[11px] font-mono text-zinc-300">
                  {data.dataset_name} · v{data.version_number}
                </span>
              )}
              {bucketKey === "__excluded__" && (
                <span className="rounded border border-amber-500/35 bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                  Excluded Records
                </span>
              )}
            </div>

            <h2 className="truncate text-lg font-bold text-white">
              {data?.block_title || blockTitle || "Block Lineage"}
            </h2>
            <p className="text-xs text-zinc-400">
              Segment:{" "}
              <strong className="text-zinc-200">
                {data?.bucket_label || bucketLabel || (bucketKey === null ? "All Contributing Rows" : bucketKey)}
              </strong>
            </p>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            {data && (
              <Link
                href={`/projects/${projectId}/datasets/${data.dataset_id}`}
                className="inline-flex items-center space-x-1.5 rounded-xl border border-zinc-700/80 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:border-zinc-600 hover:text-white transition-colors"
              >
                <span>Open Dataset Grid</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close lineage drawer"
              className="rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Metrics & Excluded Warning Strip */}
        {data && !loading && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 bg-zinc-900/40 px-6 py-3 text-xs">
            <div className="flex flex-wrap items-center gap-4">
              <span className="text-zinc-300">
                Showing <strong className="font-mono text-white">{rows.length}</strong> of{" "}
                <strong className="font-mono text-white">{data.total_matching_rows.toLocaleString()}</strong>{" "}
                matching record(s)
              </span>
              {data.highlight_columns.length > 0 && (
                <span className="text-zinc-400">
                  Highlighted:{" "}
                  <span className="text-indigo-300 font-medium">
                    {data.highlight_columns.join(", ")}
                  </span>
                </span>
              )}
            </div>

            {data.excluded_row_count > 0 && bucketKey !== "__excluded__" && onSelectExcluded && (
              <button
                type="button"
                onClick={onSelectExcluded}
                className="inline-flex items-center space-x-1.5 rounded-lg border border-amber-500/35 bg-amber-500/15 px-3 py-1.5 text-[11px] font-semibold text-amber-200 hover:bg-amber-500/25 transition-colors"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                <span>
                  Inspect {data.excluded_row_count} excluded row(s)
                  {Object.keys(data.excluded_reasons).length > 0 &&
                    ` (${Object.entries(data.excluded_reasons)
                      .map(([k, v]) => `${v} ${k.replaceAll("_", " ")}`)
                      .join(", ")})`}
                </span>
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center space-y-3 text-zinc-400">
              <Loader2 className="h-7 w-7 animate-spin text-indigo-500" />
              <p className="text-xs">Tracing contributing rows from immutable source...</p>
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
              {error}
            </div>
          ) : rows.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 p-8 text-center">
              <Table2 className="mb-3 h-7 w-7 text-zinc-600" />
              <p className="text-sm font-semibold text-zinc-300">No source rows match this selection</p>
              <p className="mt-1 text-xs text-zinc-500">
                Try inspecting excluded records if values could not be parsed.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-zinc-900/40">
                <table className="min-w-full divide-y divide-zinc-800 text-left text-xs">
                  <thead className="bg-zinc-900 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                    <tr>
                      <th className="sticky left-0 z-10 bg-zinc-900 px-3.5 py-2.5 border-r border-zinc-800">
                        Row #
                      </th>
                      {orderedColumns.map((col) => (
                        <th
                          key={col}
                          className={`whitespace-nowrap px-3.5 py-2.5 ${
                            highlightSet.has(col) ? "text-indigo-300 bg-indigo-500/10" : ""
                          }`}
                        >
                          {col}
                        </th>
                      ))}
                      <th className="whitespace-nowrap px-3.5 py-2.5">Audit Changes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/70">
                    {rows.map((row) => {
                      const changedSet = new Set(row.changed_columns);
                      return (
                        <tr key={row.row_id} className="hover:bg-zinc-900/80 transition-colors">
                          <td className="sticky left-0 z-10 bg-zinc-950/95 px-3.5 py-2.5 font-mono text-[11px] text-zinc-400 border-r border-zinc-800">
                            #{row.row_index + 1}
                          </td>
                          {orderedColumns.map((col) => {
                            const eff = row.effective_values?.[col];
                            const raw = row.raw_values?.[col];
                            const isChanged = changedSet.has(col);
                            const isHighlight = highlightSet.has(col);
                            const display =
                              eff === null || eff === undefined || String(eff).trim() === ""
                                ? "—"
                                : String(eff);

                            return (
                              <td
                                key={col}
                                className={`max-w-[240px] truncate px-3.5 py-2.5 align-top ${
                                  isHighlight ? "bg-indigo-500/5 font-medium text-white" : "text-zinc-300"
                                } ${isChanged ? "ring-1 ring-inset ring-emerald-500/30 bg-emerald-500/5" : ""}`}
                                title={
                                  isChanged
                                    ? `Cleaned from raw "${String(raw ?? "")}" -> "${display}"`
                                    : display
                                }
                              >
                                <span
                                  className={
                                    display === "—" ? "italic text-zinc-600" : ""
                                  }
                                >
                                  {display}
                                </span>
                                {isChanged && (
                                  <div className="mt-0.5 text-[10px] font-mono text-emerald-300/90">
                                    raw: {String(raw ?? "—")}
                                  </div>
                                )}
                              </td>
                            );
                          })}
                          <td className="whitespace-nowrap px-3.5 py-2.5 align-top">
                            {row.changes.length > 0 ? (
                              <div className="space-y-1">
                                {row.changes.map((ch) => (
                                  <div
                                    key={ch.id}
                                    className="inline-flex items-center space-x-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300"
                                  >
                                    <History className="h-3 w-3 shrink-0" />
                                    <span>
                                      {ch.column_name}: {ch.before ?? "∅"} → {ch.after ?? "∅"} ({ch.source})
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : row.changed_columns.length > 0 ? (
                              <span className="text-[11px] text-emerald-300">
                                {row.changed_columns.length} overlaid cell(s)
                              </span>
                            ) : (
                              <span className="text-[11px] text-zinc-600">Original</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {data && data.has_more && (
                <div className="flex justify-center pt-1">
                  <button
                    type="button"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="inline-flex items-center space-x-2 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-200 hover:border-zinc-600 hover:text-white disabled:opacity-50"
                  >
                    {loadingMore && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    <span>Load Next 50 Rows</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
