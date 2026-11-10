"use client";

import React from "react";
import { DatasetColumn, DatasetIssue } from "@/lib/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  Calendar,
  Hash,
  Info,
  Layers,
  Tag,
  Type,
  X,
} from "lucide-react";

interface ColumnProfileSidebarProps {
  column: DatasetColumn | null;
  issues: DatasetIssue[];
  loading?: boolean;
  onClose: () => void;
  onSelectIssue: (issue: DatasetIssue) => void;
}

function getTypeBadgeStyle(inferredType?: string | null): string {
  switch (inferredType) {
    case "currency":
    case "percentage":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    case "integer":
    case "decimal":
      return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    case "date":
    case "datetime":
      return "border-violet-500/30 bg-violet-500/10 text-violet-300";
    case "mixed":
      return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    case "identifier":
      return "border-zinc-600/50 bg-zinc-800 text-zinc-300";
    case "email":
    case "phone":
      return "border-sky-500/30 bg-sky-500/10 text-sky-300";
    default:
      return "border-zinc-700 bg-zinc-800/80 text-zinc-300";
  }
}

function formatNum(value?: number): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return Number.isInteger(value)
    ? value.toLocaleString()
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

interface ChartDatum {
  label: string;
  fullValue: string;
  count: number;
}

function CustomChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartDatum }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold text-white break-all">{item.fullValue}</p>
      <p className="mt-0.5 text-indigo-300">
        Count: <strong className="font-mono">{item.count.toLocaleString()}</strong>
      </p>
    </div>
  );
}

export function ColumnProfileSidebar({
  column,
  issues,
  loading = false,
  onClose,
  onSelectIssue,
}: ColumnProfileSidebarProps) {
  if (!column) return null;

  const stats = column.stats_json;
  const columnIssues = issues.filter((iss) => iss.column_id === column.id);

  const topValuesData: ChartDatum[] = (stats?.top_values || []).map((tv) => ({
    label: tv.value.length > 14 ? `${tv.value.slice(0, 12)}..` : tv.value,
    fullValue: tv.value,
    count: tv.count,
  }));

  const dateFormats = stats?.date?.formats ? Object.entries(stats.date.formats) : [];
  const formatPatterns = stats?.format_patterns
    ? Object.entries(stats.format_patterns)
    : [];

  return (
    <aside className="flex h-full w-full flex-col border-l border-zinc-800 bg-zinc-900/70 backdrop-blur-sm lg:w-[370px] xl:w-[400px] shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-zinc-800 px-4 py-3.5">
        <div className="min-w-0 pr-3">
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
              Column Profile
            </span>
            {column.semantic_hint && (
              <span className="inline-flex items-center space-x-1 rounded-md border border-indigo-500/25 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300">
                <Tag className="h-2.5 w-2.5" />
                <span>{column.semantic_hint}</span>
              </span>
            )}
          </div>
          <h3 className="mt-1 truncate text-base font-bold text-white" title={column.name}>
            {column.name}
          </h3>
          <div className="mt-1.5 flex items-center space-x-2">
            <span
              className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${getTypeBadgeStyle(
                column.inferred_type
              )}`}
            >
              {column.inferred_type || "unprofiled"}
            </span>
            <span className="text-[11px] text-zinc-500">Col #{column.position + 1}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
          aria-label="Close column profile"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {loading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-20 rounded-xl bg-zinc-800/70" />
            <div className="h-40 rounded-xl bg-zinc-800/70" />
          </div>
        ) : !stats ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/50 p-6 text-center text-xs text-zinc-400">
            <Info className="mb-2 h-5 w-5 text-zinc-500" />
            <p>Column profile statistics have not been generated yet.</p>
          </div>
        ) : (
          <>
            {/* Completeness & Cardinality KPIs */}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-3">
                <p className="text-[11px] text-zinc-400">Missing / Null</p>
                <p className="mt-0.5 text-base font-bold text-white">
                  {stats.null_pct !== undefined ? `${stats.null_pct}%` : "0%"}
                </p>
                <p className="mt-0.5 text-[10px] text-zinc-500">
                  {stats.empty_count ?? 0} empty • {stats.null_like_count ?? 0} null-like
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-3">
                <p className="text-[11px] text-zinc-400">Distinct Values</p>
                <p className="mt-0.5 text-base font-bold text-white">
                  {(stats.distinct_count ?? 0).toLocaleString()}
                </p>
                <p className="mt-0.5 text-[10px] text-zinc-500">
                  of {(stats.non_null_count ?? 0).toLocaleString()} non-null
                </p>
              </div>
            </div>

            {/* Date Profile & Mixed / Ambiguous Format Alerts */}
            {stats.date && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-violet-300">
                    <Calendar className="h-3.5 w-3.5" />
                    <span>Detected Date Formats</span>
                  </div>
                  {(dateFormats.length > 1 || (stats.date.ambiguous_count ?? 0) > 0) && (
                    <span className="inline-flex items-center space-x-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                      <AlertTriangle className="h-3 w-3" />
                      <span>Mixed / Ambiguous</span>
                    </span>
                  )}
                </div>

                {(stats.date.ambiguous_count ?? 0) > 0 && (
                  <p className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-1.5 text-[11px] text-amber-200">
                    {stats.date.ambiguous_count} value(s) are ambiguous (MM/DD vs DD/MM) and were not silently guessed.
                  </p>
                )}

                <div className="space-y-1.5">
                  {dateFormats.map(([fmt, count]) => (
                    <div
                      key={fmt}
                      className="flex items-center justify-between rounded-lg bg-zinc-900/90 px-2.5 py-1.5 text-xs"
                    >
                      <code className="font-mono text-[11px] text-zinc-200">{fmt}</code>
                      <span className="font-semibold text-violet-300">{count}</span>
                    </div>
                  ))}
                </div>

                {(stats.date.min || stats.date.max) && (
                  <div className="flex items-center justify-between border-t border-zinc-800/80 pt-2 text-[11px] text-zinc-400">
                    <span>Range (unambiguous):</span>
                    <span className="font-mono text-zinc-200">
                      {stats.date.min || "?"} → {stats.date.max || "?"}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Numeric Stats */}
            {stats.numeric && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-indigo-300">
                    <Hash className="h-3.5 w-3.5" />
                    <span>Numeric Summary</span>
                  </div>
                  {(stats.numeric.invalid_count ?? 0) > 0 && (
                    <span className="rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-300">
                      {stats.numeric.invalid_count} invalid
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Min</span>
                    <span className="font-mono text-zinc-100">{formatNum(stats.numeric.min)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Max</span>
                    <span className="font-mono text-zinc-100">{formatNum(stats.numeric.max)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Mean</span>
                    <span className="font-mono text-zinc-100">{formatNum(stats.numeric.mean)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Median</span>
                    <span className="font-mono text-zinc-100">{formatNum(stats.numeric.median)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Sum</span>
                    <span className="font-mono text-emerald-300">{formatNum(stats.numeric.sum)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">IQR</span>
                    <span className="font-mono text-zinc-100">{formatNum(stats.numeric.iqr)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Text Stats */}
            {stats.text && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3.5 space-y-2.5">
                <div className="flex items-center space-x-2 text-xs font-semibold text-zinc-200">
                  <Type className="h-3.5 w-3.5 text-sky-400" />
                  <span>Text &amp; Formatting</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
                  <div className="rounded-lg bg-zinc-900 p-2">
                    <p className="text-zinc-500">Min Len</p>
                    <p className="font-mono font-semibold text-white">{stats.text.min_length ?? 0}</p>
                  </div>
                  <div className="rounded-lg bg-zinc-900 p-2">
                    <p className="text-zinc-500">Avg Len</p>
                    <p className="font-mono font-semibold text-white">{stats.text.avg_length ?? 0}</p>
                  </div>
                  <div className="rounded-lg bg-zinc-900 p-2">
                    <p className="text-zinc-500">Max Len</p>
                    <p className="font-mono font-semibold text-white">{stats.text.max_length ?? 0}</p>
                  </div>
                </div>
                {(stats.text.whitespace_count ?? 0) > 0 && (
                  <p className="text-[11px] text-amber-300">
                    {stats.text.whitespace_count} value(s) ({stats.text.whitespace_pct}%) have leading/trailing whitespace.
                  </p>
                )}
                {stats.text.case_distribution && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(stats.text.case_distribution)
                      .filter(([, cnt]) => cnt > 0)
                      .map(([style, cnt]) => (
                        <span
                          key={style}
                          className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-300"
                        >
                          {style}: <strong className="text-white">{cnt}</strong>
                        </span>
                      ))}
                  </div>
                )}
              </div>
            )}

            {/* Top Values Distribution Chart */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-semibold text-zinc-200">
                  <Layers className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Top Values Distribution</span>
                </div>
                <span className="text-[10px] text-zinc-500">Top {topValuesData.length}</span>
              </div>

              {topValuesData.length === 0 ? (
                <p className="py-4 text-center text-xs text-zinc-500">No non-null values present.</p>
              ) : (
                <div className="h-48 w-full min-w-0">
                  <ResponsiveContainer width="100%" height={192}>
                    <BarChart
                      data={topValuesData}
                      layout="vertical"
                      margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="label"
                        width={96}
                        tick={{ fill: "#a1a1aa", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip content={<CustomChartTooltip />} cursor={{ fill: "rgba(99, 102, 241, 0.1)" }} />
                      <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} maxBarSize={18} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Format Patterns */}
            {formatPatterns.length > 0 && (
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  Value Shapes ({formatPatterns.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {formatPatterns.slice(0, 10).map(([pattern, cnt]) => (
                    <span
                      key={pattern}
                      className="rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1 font-mono text-[10px] text-zinc-300"
                    >
                      {pattern} <span className="text-indigo-400">×{cnt}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Column Issues */}
            {columnIssues.length > 0 && (
              <div className="space-y-2 border-t border-zinc-800 pt-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  Column Issues ({columnIssues.length})
                </p>
                <div className="space-y-2">
                  {columnIssues.map((iss) => (
                    <button
                      key={iss.id}
                      type="button"
                      onClick={() => onSelectIssue(iss)}
                      className="w-full rounded-xl border border-zinc-800 bg-zinc-950/70 p-2.5 text-left text-xs transition-colors hover:border-indigo-500/40 hover:bg-zinc-900"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white">{iss.type.replaceAll("_", " ")}</span>
                        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300">
                          {iss.affected_count} rows
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-zinc-400">{iss.description}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
