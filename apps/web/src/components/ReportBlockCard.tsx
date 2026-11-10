"use client";

import React from "react";
import { ComputedBlock, DataQualityCaveat, NarrativeContent } from "@/lib/api";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Edit3,
  Layers,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";

const CHART_COLORS = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ec4899",
  "#06b6d4",
  "#8b5cf6",
  "#f97316",
  "#84cc16",
  "#38bdf8",
  "#e11d48",
];

interface ChartDatumItem {
  bucket_key: string;
  label: string;
  value: number;
  formatted_value?: string;
  mean_value?: number | null;
  formatted_mean?: string;
  secondary_value?: number | null;
  row_count: number;
  valid_metric_count?: number;
  excluded_rows?: number;
  share_pct?: number;
}

interface ReportBlockCardProps {
  block: ComputedBlock;
  index: number;
  totalBlocks: number;
  presentationMode: boolean;
  canEdit: boolean;
  regeneratingNarrative?: boolean;
  onInspectLineage: (
    blockId: string,
    blockTitle: string,
    bucketKey: string | null,
    bucketLabel: string | null
  ) => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  onRegenerateNarrative?: () => void;
}

function getWidthClass(width: string | undefined, type: string): string {
  if (width === "third") return "lg:col-span-4";
  if (width === "half") return "lg:col-span-6";
  if (type === "kpi" && !width) return "lg:col-span-4";
  return "lg:col-span-12";
}

function CustomSeriesTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartDatumItem }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white shadow-xl">
      <p className="font-semibold text-white">{item.label}</p>
      <p className="mt-1 font-mono text-indigo-300 font-bold">
        {item.formatted_value ?? item.value}
      </p>
      <p className="mt-0.5 text-[11px] text-zinc-400">
        {item.row_count} row(s)
        {item.share_pct !== undefined ? ` · ${item.share_pct}% share` : ""}
      </p>
      <p className="mt-1 text-[10px] text-indigo-400">Click to inspect source rows</p>
    </div>
  );
}

function ReadinessBadge({ readiness }: { readiness?: string }) {
  if (readiness === "verified") {
    return (
      <span className="inline-flex items-center space-x-1 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300 print:border-emerald-700 print:text-emerald-800">
        <ShieldCheck className="h-3.5 w-3.5" />
        <span>Verified Quality</span>
      </span>
    );
  }
  if (readiness === "caution") {
    return (
      <span className="inline-flex items-center space-x-1 rounded-full border border-rose-500/30 bg-rose-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-rose-300 print:border-rose-700 print:text-rose-800">
        <ShieldAlert className="h-3.5 w-3.5" />
        <span>Caution Required</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center space-x-1 rounded-full border border-amber-500/30 bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300 print:border-amber-700 print:text-amber-800">
      <AlertTriangle className="h-3.5 w-3.5" />
      <span>Needs Review</span>
    </span>
  );
}

function severityPillClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "border-rose-500/35 bg-rose-500/15 text-rose-300 print:border-rose-600 print:text-rose-800";
    case "high":
      return "border-orange-500/35 bg-orange-500/15 text-orange-300 print:border-orange-600 print:text-orange-800";
    case "medium":
      return "border-amber-500/35 bg-amber-500/15 text-amber-300 print:border-amber-600 print:text-amber-800";
    default:
      return "border-sky-500/35 bg-sky-500/15 text-sky-300 print:border-sky-600 print:text-sky-800";
  }
}

export function ReportBlockCard({
  block,
  index,
  totalBlocks,
  presentationMode,
  canEdit,
  regeneratingNarrative = false,
  onInspectLineage,
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  onRegenerateNarrative,
}: ReportBlockCardProps) {
  const spanClass = getWidthClass(block.width, block.type);
  const data = (block.data || {}) as Record<string, unknown>;
  const showEditorTools = canEdit && !presentationMode;

  const isTraceable = [
    "kpi",
    "bar_chart",
    "pie_chart",
    "line_chart",
    "area_chart",
    "summary_table",
  ].includes(block.type);

  return (
    <section
      className={`${spanClass} group flex flex-col rounded-2xl border border-zinc-800/90 bg-zinc-900/60 p-5 shadow-lg transition-all hover:border-zinc-700/90 print:break-inside-avoid print:border-slate-300 print:bg-white print:text-slate-900 print:shadow-none`}
    >
      {/* Card Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-bold tracking-tight text-white print:text-slate-900">
              {block.title}
            </h3>
            {block.type === "narrative" && (
              <span className="inline-flex items-center space-x-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-300 print:hidden">
                <Sparkles className="h-2.5 w-2.5" />
                <span>Briefing</span>
              </span>
            )}
          </div>
          {block.subtitle && (
            <p className="mt-0.5 text-xs text-zinc-400 print:text-slate-600">
              {block.subtitle}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-1 shrink-0 print:hidden">
          {isTraceable && (
            <button
              type="button"
              onClick={() => onInspectLineage(block.id, block.title, null, "All Contributing Rows")}
              title="Inspect underlying source rows"
              className="inline-flex items-center space-x-1 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2 py-1 text-[11px] font-medium text-zinc-400 hover:border-indigo-500/40 hover:text-indigo-300 transition-colors"
            >
              <Layers className="h-3 w-3" />
              <span className="hidden sm:inline">Lineage</span>
            </button>
          )}

          {block.type === "narrative" && showEditorTools && onRegenerateNarrative && (
            <button
              type="button"
              onClick={onRegenerateNarrative}
              disabled={regeneratingNarrative}
              className="inline-flex items-center space-x-1 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 text-[11px] font-semibold text-indigo-300 hover:bg-indigo-500/20 disabled:opacity-50"
            >
              {regeneratingNarrative ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              <span>{regeneratingNarrative ? "Synthesizing..." : "Regenerate"}</span>
            </button>
          )}

          {showEditorTools && (
            <>
              <button
                type="button"
                disabled={index === 0}
                onClick={onMoveUp}
                aria-label="Move block up"
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1.5 text-zinc-400 hover:text-white disabled:opacity-30"
              >
                <ArrowUp className="h-3 w-3" />
              </button>
              <button
                type="button"
                disabled={index >= totalBlocks - 1}
                onClick={onMoveDown}
                aria-label="Move block down"
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1.5 text-zinc-400 hover:text-white disabled:opacity-30"
              >
                <ArrowDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={onEdit}
                aria-label="Configure block"
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1.5 text-zinc-400 hover:text-indigo-300"
              >
                <Edit3 className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={onDelete}
                aria-label="Remove block"
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-1.5 text-zinc-400 hover:text-rose-400"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Block Body */}
      {block.type === "kpi" && <KpiBlockView block={block} data={data} onInspectLineage={onInspectLineage} />}
      {block.type === "bar_chart" && <BarBlockView block={block} data={data} onInspectLineage={onInspectLineage} />}
      {block.type === "pie_chart" && <PieBlockView block={block} data={data} onInspectLineage={onInspectLineage} />}
      {(block.type === "line_chart" || block.type === "area_chart") && (
        <TimeSeriesBlockView block={block} data={data} onInspectLineage={onInspectLineage} />
      )}
      {block.type === "summary_table" && (
        <SummaryTableBlockView block={block} data={data} onInspectLineage={onInspectLineage} />
      )}
      {block.type === "narrative" && (
        <NarrativeBlockView narrative={block.data as NarrativeContent | null} />
      )}
      {block.type === "data_quality" && <DataQualityBlockView data={data} />}
    </section>
  );
}

function KpiBlockView({
  block,
  data,
  onInspectLineage,
}: {
  block: ComputedBlock;
  data: Record<string, unknown>;
  onInspectLineage: ReportBlockCardProps["onInspectLineage"];
}) {
  const formatted = String(data.formatted_value ?? "—");
  const matchingRows = Number(data.matching_rows ?? 0);
  const excludedRows = Number(data.excluded_rows ?? 0);
  const agg = String(data.aggregation ?? "count");
  const metricCol = data.metric_column ? String(data.metric_column) : null;

  return (
    <div className="flex flex-1 flex-col justify-between space-y-3">
      <button
        type="button"
        onClick={() => onInspectLineage(block.id, block.title, null, block.title)}
        className="text-left rounded-xl p-1 -m-1 transition-colors hover:bg-zinc-800/40 focus:outline-none"
      >
        <div className="text-3xl sm:text-4xl font-black tracking-tight text-white font-mono print:text-slate-900">
          {formatted}
        </div>
        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-500 print:text-slate-600">
          {metricCol ? `${agg} of ${metricCol}` : "row count"}
        </div>
      </button>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 pt-2.5 text-[11px] print:border-slate-200">
        <button
          type="button"
          onClick={() => onInspectLineage(block.id, block.title, null, block.title)}
          className="text-zinc-400 hover:text-indigo-300 transition-colors print:text-slate-600"
        >
          <strong className="font-mono text-zinc-200 print:text-slate-900">
            {matchingRows.toLocaleString()}
          </strong>{" "}
          contributing row(s)
        </button>

        {excludedRows > 0 && (
          <button
            type="button"
            onClick={() =>
              onInspectLineage(block.id, block.title, "__excluded__", "Excluded / Unparseable Rows")
            }
            className="inline-flex items-center space-x-1 rounded-md border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300 hover:bg-amber-500/25 print:border-amber-600 print:text-amber-800"
          >
            <AlertTriangle className="h-3 w-3" />
            <span>{excludedRows} excluded</span>
          </button>
        )}
      </div>
    </div>
  );
}

function BarBlockView({
  block,
  data,
  onInspectLineage,
}: {
  block: ComputedBlock;
  data: Record<string, unknown>;
  onInspectLineage: ReportBlockCardProps["onInspectLineage"];
}) {
  const items = ((data.items as ChartDatumItem[]) || []).map((it) => ({
    ...it,
    shortLabel: it.label.length > 16 ? `${it.label.slice(0, 14)}..` : it.label,
  }));
  const excludedRows = Number(data.excluded_rows ?? 0);

  if (items.length === 0) {
    return (
      <div className="flex h-52 items-center justify-center rounded-xl border border-dashed border-zinc-800 text-xs text-zinc-500">
        No categorical breakdown available for this column configuration.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={items} margin={{ top: 10, right: 14, left: 4, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis
              dataKey="shortLabel"
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              interval={0}
              angle={items.length > 6 ? -20 : 0}
              textAnchor={items.length > 6 ? "end" : "middle"}
            />
            <YAxis
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={62}
            />
            <Tooltip content={<CustomSeriesTooltip />} cursor={{ fill: "rgba(99, 102, 241, 0.08)" }} />
            <Bar
              dataKey="value"
              radius={[6, 6, 0, 0]}
              className="cursor-pointer"
              onClick={(_barData, idx) => {
                const target = items[idx];
                if (target) {
                  onInspectLineage(block.id, block.title, target.bucket_key, target.label);
                }
              }}
            >
              {items.map((entry, idx) => (
                <Cell
                  key={entry.bucket_key}
                  fill={CHART_COLORS[idx % CHART_COLORS.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 print:hidden">
        <div className="flex flex-wrap gap-1.5">
          {items.slice(0, 6).map((it, idx) => (
            <button
              key={it.bucket_key}
              type="button"
              onClick={() => onInspectLineage(block.id, block.title, it.bucket_key, it.label)}
              className="inline-flex items-center space-x-1.5 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2 py-1 text-[11px] text-zinc-300 hover:border-indigo-500/40 hover:text-white transition-colors"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
              />
              <span>{it.label}:</span>
              <strong className="font-mono text-white">{it.formatted_value ?? it.value}</strong>
            </button>
          ))}
        </div>
        {excludedRows > 0 && (
          <button
            type="button"
            onClick={() => onInspectLineage(block.id, block.title, "__excluded__", "Excluded Rows")}
            className="text-[11px] text-amber-300 hover:underline"
          >
            {excludedRows} excluded row(s)
          </button>
        )}
      </div>
    </div>
  );
}

function PieBlockView({
  block,
  data,
  onInspectLineage,
}: {
  block: ComputedBlock;
  data: Record<string, unknown>;
  onInspectLineage: ReportBlockCardProps["onInspectLineage"];
}) {
  const items = (data.items as ChartDatumItem[]) || [];

  if (items.length === 0) {
    return (
      <div className="flex h-52 items-center justify-center rounded-xl border border-dashed border-zinc-800 text-xs text-zinc-500">
        No categorical share data available.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 items-center">
      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={86}
              paddingAngle={2}
              className="cursor-pointer"
              onClick={(_sector, idx) => {
                const target = items[idx];
                if (target) {
                  onInspectLineage(block.id, block.title, target.bucket_key, target.label);
                }
              }}
            >
              {items.map((entry, idx) => (
                <Cell
                  key={entry.bucket_key}
                  fill={CHART_COLORS[idx % CHART_COLORS.length]}
                  stroke="#09090b"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomSeriesTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
        {items.map((it, idx) => (
          <button
            key={it.bucket_key}
            type="button"
            onClick={() => onInspectLineage(block.id, block.title, it.bucket_key, it.label)}
            className="flex w-full items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-3 py-1.5 text-left text-xs transition-colors hover:border-indigo-500/40 hover:bg-zinc-900 print:border-slate-200 print:bg-slate-50"
          >
            <span className="flex items-center space-x-2 min-w-0 pr-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
              />
              <span className="truncate font-medium text-zinc-200 print:text-slate-800">
                {it.label}
              </span>
            </span>
            <span className="shrink-0 font-mono text-[11px] text-zinc-300 print:text-slate-900">
              {it.formatted_value ?? it.value}{" "}
              <span className="text-zinc-500">({it.share_pct ?? 0}%)</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function TimeSeriesBlockView({
  block,
  data,
  onInspectLineage,
}: {
  block: ComputedBlock;
  data: Record<string, unknown>;
  onInspectLineage: ReportBlockCardProps["onInspectLineage"];
}) {
  const points = (data.points as ChartDatumItem[]) || [];
  const ambiguousSkipped = Number(data.ambiguous_skipped_count ?? 0);
  const unparseableSkipped = Number(data.unparseable_skipped_count ?? 0);
  const skippedTotal = ambiguousSkipped + unparseableSkipped;

  if (points.length === 0) {
    return (
      <div className="flex h-52 flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 p-4 text-center text-xs text-zinc-500">
        <p>No valid unambiguous chronological points could be plotted.</p>
        {skippedTotal > 0 && (
          <button
            type="button"
            onClick={() =>
              onInspectLineage(block.id, block.title, "__excluded__", "Ambiguous / Unparseable Dates")
            }
            className="mt-2 text-amber-300 hover:underline"
          >
            Inspect {skippedTotal} skipped date row(s)
          </button>
        )}
      </div>
    );
  }

  const handleChartClick = (state: { activeTooltipIndex?: number | string | null }) => {
    const idx =
      typeof state?.activeTooltipIndex === "number"
        ? state.activeTooltipIndex
        : Number(state?.activeTooltipIndex);
    if (!Number.isNaN(idx) && points[idx]) {
      onInspectLineage(block.id, block.title, points[idx].bucket_key, points[idx].label);
    }
  };

  return (
    <div className="space-y-3">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {block.type === "area_chart" ? (
            <AreaChart data={points} margin={{ top: 10, right: 16, left: 4, bottom: 10 }} onClick={handleChartClick}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={{ stroke: "#3f3f46" }} tickLine={false} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={false} tickLine={false} width={64} />
              <Tooltip content={<CustomSeriesTooltip />} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#6366f1"
                strokeWidth={2.5}
                fill="#6366f1"
                fillOpacity={0.18}
              />
            </AreaChart>
          ) : (
            <LineChart data={points} margin={{ top: 10, right: 16, left: 4, bottom: 10 }} onClick={handleChartClick}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={{ stroke: "#3f3f46" }} tickLine={false} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={false} tickLine={false} width={64} />
              <Tooltip content={<CustomSeriesTooltip />} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#818cf8"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#6366f1", stroke: "#09090b", strokeWidth: 2 }}
                activeDot={{ r: 6, fill: "#a5b4fc" }}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>

      {skippedTotal > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200 print:border-amber-600 print:text-amber-900 print:bg-amber-50">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
            <span>
              {ambiguousSkipped > 0
                ? `${ambiguousSkipped} ambiguous date(s) excluded (never silently guessed). `
                : ""}
              {unparseableSkipped > 0 ? `${unparseableSkipped} unparseable date(s) skipped.` : ""}
            </span>
          </div>
          <button
            type="button"
            onClick={() =>
              onInspectLineage(block.id, block.title, "__excluded__", "Skipped Ambiguous / Unparseable Dates")
            }
            className="font-semibold text-amber-300 hover:underline print:hidden"
          >
            Inspect skipped rows
          </button>
        </div>
      )}
    </div>
  );
}

function SummaryTableBlockView({
  block,
  data,
  onInspectLineage,
}: {
  block: ComputedBlock;
  data: Record<string, unknown>;
  onInspectLineage: ReportBlockCardProps["onInspectLineage"];
}) {
  const rows = (data.rows as ChartDatumItem[]) || [];
  const dimCol = String(data.dimension_column || "Segment");
  const metricCol = data.metric_column ? String(data.metric_column) : null;
  const secCol = data.secondary_metric_column ? String(data.secondary_metric_column) : null;

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-800 p-6 text-center text-xs text-zinc-500">
        No rows to summarize for this configuration.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800/80 print:border-slate-300">
      <table className="min-w-full divide-y divide-zinc-800 text-left text-xs print:divide-slate-300">
        <thead className="bg-zinc-950/70 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 print:bg-slate-100 print:text-slate-700">
          <tr>
            <th className="px-4 py-2.5">{dimCol}</th>
            <th className="px-4 py-2.5 text-right">Records</th>
            <th className="px-4 py-2.5 text-right">{metricCol || "Count"}</th>
            {metricCol && <th className="px-4 py-2.5 text-right">Avg {metricCol}</th>}
            {secCol && <th className="px-4 py-2.5 text-right">{secCol}</th>}
            <th className="px-4 py-2.5 text-right">Share</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/70 print:divide-slate-200">
          {rows.map((r) => (
            <tr
              key={r.bucket_key}
              onClick={() => onInspectLineage(block.id, block.title, r.bucket_key, r.label)}
              className="cursor-pointer transition-colors hover:bg-indigo-500/10"
              title="Click to trace contributing source rows"
            >
              <td className="px-4 py-2.5 font-medium text-white print:text-slate-900">
                {r.label}
              </td>
              <td className="px-4 py-2.5 text-right font-mono text-zinc-300 print:text-slate-700">
                {r.row_count.toLocaleString()}
              </td>
              <td className="px-4 py-2.5 text-right font-mono font-semibold text-indigo-300 print:text-slate-900">
                {r.formatted_value ?? r.value}
              </td>
              {metricCol && (
                <td className="px-4 py-2.5 text-right font-mono text-zinc-400 print:text-slate-700">
                  {r.formatted_mean ?? "—"}
                </td>
              )}
              {secCol && (
                <td className="px-4 py-2.5 text-right font-mono text-zinc-300 print:text-slate-700">
                  {r.secondary_value !== null && r.secondary_value !== undefined
                    ? r.secondary_value.toLocaleString()
                    : "—"}
                </td>
              )}
              <td className="px-4 py-2.5 text-right font-mono text-zinc-400 print:text-slate-700">
                {r.share_pct ?? 0}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NarrativeBlockView({ narrative }: { narrative: NarrativeContent | null }) {
  if (!narrative || !narrative.headline) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 p-6 text-center text-xs text-zinc-400">
        No executive briefing generated yet. Click <strong>Regenerate</strong> to synthesize a verified summary from backend metrics.
      </div>
    );
  }

  const verif = narrative.verification;

  return (
    <div className="space-y-4">
      {/* Grounding Verification Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/60 px-3.5 py-2 text-[11px] print:border-slate-300 print:bg-slate-50">
        <div className="flex items-center space-x-2">
          {verif?.verified ? (
            <>
              <ShieldCheck className="h-4 w-4 text-emerald-400 print:text-emerald-700" />
              <span className="font-semibold text-emerald-300 print:text-emerald-800">
                Backend-Verified Narrative
              </span>
              <span className="text-zinc-400 print:text-slate-600">
                ({verif.total_numbers_checked} numeric citation(s) verified against computed metrics)
              </span>
            </>
          ) : (
            <>
              <ShieldAlert className="h-4 w-4 text-amber-400" />
              <span className="font-semibold text-amber-300">
                Numeric Grounding Check Flagged Unverified Figure(s):{" "}
                {verif?.unverified_numbers?.join(", ")}
              </span>
            </>
          )}
        </div>
        {narrative.provider && (
          <span className="font-mono text-[10px] uppercase text-zinc-500 print:text-slate-600">
            {narrative.provider} · {narrative.model || "default"}
          </span>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="text-lg font-bold tracking-tight text-white print:text-slate-950">
          {narrative.headline}
        </h4>
        <p className="text-sm leading-relaxed text-zinc-300 print:text-slate-800">
          {narrative.executive_summary}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 pt-1">
        {narrative.key_findings?.length > 0 && (
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-3.5 print:border-slate-200 print:bg-slate-50">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-emerald-400 print:text-emerald-800">
              Key Findings
            </p>
            <ul className="space-y-1.5 text-xs text-zinc-300 print:text-slate-800">
              {narrative.key_findings.map((item, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400 print:text-emerald-700" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {narrative.recommendations?.length > 0 && (
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-3.5 print:border-slate-200 print:bg-slate-50">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-indigo-400 print:text-indigo-800">
              Analyst Recommendations
            </p>
            <ul className="space-y-1.5 text-xs text-zinc-300 print:text-slate-800">
              {narrative.recommendations.map((item, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400 print:bg-indigo-700" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {narrative.caveats?.length > 0 && (
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-3.5 print:border-slate-200 print:bg-slate-50">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-amber-400 print:text-amber-800">
              Caveats &amp; Risks
            </p>
            <ul className="space-y-1.5 text-xs text-zinc-300 print:text-slate-800">
              {narrative.caveats.map((item, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400 print:text-amber-700" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function DataQualityBlockView({ data }: { data: Record<string, unknown> }) {
  const overview = (data.overview as Record<string, unknown>) || {};
  const caveats = (data.caveats as DataQualityCaveat[]) || [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/60 p-3.5 print:border-slate-300 print:bg-slate-50">
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <ReadinessBadge readiness={String(overview.readiness || "needs_review")} />
          <span className="text-zinc-300 print:text-slate-800">
            Completeness:{" "}
            <strong className="font-mono">{String(overview.completeness_pct ?? 100)}%</strong>
          </span>
          <span className="text-zinc-300 print:text-slate-800">
            Open Issues:{" "}
            <strong className="font-mono">{String(overview.open_issues_count ?? 0)}</strong>
          </span>
          <span className="text-zinc-300 print:text-slate-800">
            Readiness Score:{" "}
            <strong className="font-mono">{String(overview.readiness_score ?? 0)}/100</strong>
          </span>
        </div>
      </div>

      {caveats.length === 0 ? (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300 print:text-emerald-800">
          No open structural data-quality caveats detected for this dataset version.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
          {caveats.map((cav) => (
            <div
              key={cav.id}
              className="rounded-xl border border-zinc-800/80 bg-zinc-950/50 p-3 print:border-slate-300 print:bg-white"
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${severityPillClass(cav.severity)}`}>
                  {cav.severity}
                </span>
                {cav.column && (
                  <span className="font-mono text-[11px] text-zinc-400 print:text-slate-600">
                    {cav.column}
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-xs font-semibold text-white print:text-slate-900">
                {cav.title}
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-zinc-400 print:text-slate-700">
                {cav.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
