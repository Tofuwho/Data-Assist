"use client";

import React, { useMemo, useState } from "react";
import { DatasetColumn, DatasetIssue } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Eye,
  Filter,
  Info,
  Loader2,
  X,
} from "lucide-react";

interface IssuesPanelProps {
  issues: DatasetIssue[];
  columns: DatasetColumn[];
  activeIssueId: string | null;
  loading?: boolean;
  error?: string | null;
  onSelectIssue: (issue: DatasetIssue | null) => void;
  onInspectColumn: (columnId: string) => void;
  onClose?: () => void;
}

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

function getSeverityMeta(severity: string) {
  switch (severity) {
    case "critical":
      return {
        label: "Critical",
        badge: "border-rose-500/35 bg-rose-500/15 text-rose-300",
        ring: "border-rose-500/50 bg-rose-500/10",
        dot: "bg-rose-500",
        icon: AlertCircle,
      };
    case "high":
      return {
        label: "High",
        badge: "border-orange-500/35 bg-orange-500/15 text-orange-300",
        ring: "border-orange-500/50 bg-orange-500/10",
        dot: "bg-orange-500",
        icon: AlertTriangle,
      };
    case "medium":
      return {
        label: "Medium",
        badge: "border-amber-500/35 bg-amber-500/15 text-amber-300",
        ring: "border-amber-500/50 bg-amber-500/10",
        dot: "bg-amber-500",
        icon: AlertTriangle,
      };
    default:
      return {
        label: "Low",
        badge: "border-sky-500/35 bg-sky-500/15 text-sky-300",
        ring: "border-sky-500/50 bg-sky-500/10",
        dot: "bg-sky-500",
        icon: Info,
      };
  }
}

function summarizeDetails(details: Record<string, unknown> | null): string[] {
  if (!details) return [];
  const snippets: string[] = [];

  if (Array.isArray(details.formats)) {
    const fmts = details.formats
      .slice(0, 4)
      .map((f) => {
        if (typeof f === "object" && f !== null && "format" in f) {
          const obj = f as { format?: string; count?: number };
          return `${obj.format} (${obj.count ?? ""})`;
        }
        return String(f);
      });
    if (fmts.length > 0) snippets.push(`Formats: ${fmts.join(", ")}`);
  }

  if (Array.isArray(details.clusters)) {
    const clusters = details.clusters.slice(0, 2).map((c) => {
      if (typeof c === "object" && c !== null && "variants" in c) {
        const obj = c as { canonical?: string; variants?: string[] };
        return `[${(obj.variants || []).slice(0, 3).join(" / ")}]`;
      }
      return String(c);
    });
    if (clusters.length > 0) snippets.push(`Variants: ${clusters.join("; ")}`);
  }

  if (Array.isArray(details.examples)) {
    const ex = details.examples.slice(0, 4).map((item) => {
      if (typeof item === "object" && item !== null && "value" in item) {
        return String((item as { value?: unknown }).value);
      }
      return String(item);
    });
    if (ex.length > 0) snippets.push(`Examples: ${ex.join(", ")}`);
  }

  if (Array.isArray(details.outliers)) {
    const vals = details.outliers
      .slice(0, 3)
      .map((item) =>
        typeof item === "object" && item !== null && "value" in item
          ? String((item as { value?: unknown }).value)
          : String(item)
      );
    if (vals.length > 0) snippets.push(`Outliers: ${vals.join(", ")}`);
  }

  return snippets;
}

export function IssuesPanel({
  issues,
  columns,
  activeIssueId,
  loading = false,
  error = null,
  onSelectIssue,
  onInspectColumn,
  onClose,
}: IssuesPanelProps) {
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [columnFilter, setColumnFilter] = useState<string>("all");

  const columnsById = useMemo(() => {
    const map = new Map<string, DatasetColumn>();
    columns.forEach((c) => map.set(c.id, c));
    return map;
  }, [columns]);

  const distinctTypes = useMemo(() => {
    return Array.from(new Set(issues.map((i) => i.type))).sort();
  }, [issues]);

  const filteredIssues = useMemo(() => {
    return issues.filter((iss) => {
      if (severityFilter !== "all" && iss.severity !== severityFilter) return false;
      if (typeFilter !== "all" && iss.type !== typeFilter) return false;
      if (columnFilter === "__dataset__" && iss.column_id !== null) return false;
      if (
        columnFilter !== "all" &&
        columnFilter !== "__dataset__" &&
        iss.column_id !== columnFilter
      ) {
        return false;
      }
      return true;
    });
  }, [issues, severityFilter, typeFilter, columnFilter]);

  const groupedBySeverity = useMemo(() => {
    return SEVERITY_ORDER.map((sev) => ({
      severity: sev,
      items: filteredIssues.filter((i) => i.severity === sev),
    })).filter((g) => g.items.length > 0);
  }, [filteredIssues]);

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { all: issues.length, critical: 0, high: 0, medium: 0, low: 0 };
    issues.forEach((i) => {
      counts[i.severity] = (counts[i.severity] || 0) + 1;
    });
    return counts;
  }, [issues]);

  return (
    <aside className="flex h-full w-full flex-col border-r border-zinc-800 bg-zinc-900/70 backdrop-blur-sm lg:w-[340px] xl:w-[360px] shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3.5">
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-amber-400" />
          <h3 className="text-sm font-bold text-white">Detected Issues</h3>
          <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[11px] font-semibold text-zinc-200">
            {filteredIssues.length}
          </span>
        </div>

        <div className="flex items-center space-x-1">
          {activeIssueId && (
            <button
              type="button"
              onClick={() => onSelectIssue(null)}
              className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[11px] font-semibold text-indigo-300 hover:bg-indigo-500/20 transition-colors"
            >
              Reset focus
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
              aria-label="Collapse issues panel"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="space-y-2.5 border-b border-zinc-800/80 bg-zinc-950/40 px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          {(["all", ...SEVERITY_ORDER] as const).map((sev) => {
            const active = severityFilter === sev;
            const count = severityCounts[sev] || 0;
            if (sev !== "all" && count === 0) return null;
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSeverityFilter(sev)}
                className={`rounded-lg border px-2 py-1 text-[11px] font-semibold capitalize transition-colors ${
                  active
                    ? "border-indigo-500/50 bg-indigo-600/20 text-indigo-200"
                    : "border-zinc-800 bg-zinc-900/70 text-zinc-400 hover:text-white"
                }`}
              >
                {sev} ({count})
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <select
            aria-label="Filter by issue type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-[11px] text-zinc-200 focus:border-indigo-500 focus:outline-none"
          >
            <option value="all">All issue types</option>
            {distinctTypes.map((t) => (
              <option key={t} value={t}>
                {t.replaceAll("_", " ")}
              </option>
            ))}
          </select>

          <select
            aria-label="Filter by column"
            value={columnFilter}
            onChange={(e) => setColumnFilter(e.target.value)}
            className="rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-[11px] text-zinc-200 focus:border-indigo-500 focus:outline-none"
          >
            <option value="all">All columns</option>
            <option value="__dataset__">Dataset-level only</option>
            {columns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Issue List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12 text-xs text-zinc-400">
            <Loader2 className="mb-2 h-6 w-6 animate-spin text-indigo-500" />
            <span>Loading issues...</span>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 p-3 text-xs text-rose-300">
            {error}
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 p-8 text-center">
            <CheckCircle2 className="mb-2 h-7 w-7 text-emerald-400" />
            <p className="text-xs font-semibold text-white">
              {issues.length === 0 ? "No issues detected" : "No matching issues"}
            </p>
            <p className="mt-1 text-[11px] text-zinc-400">
              {issues.length === 0
                ? "This dataset passed all deterministic quality checks cleanly."
                : "Try clearing one of the filters above."}
            </p>
          </div>
        ) : (
          groupedBySeverity.map((group) => {
            const meta = getSeverityMeta(group.severity);
            return (
              <div key={group.severity} className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <span className="flex items-center space-x-1.5 text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
                    <span>{meta.label} Severity</span>
                  </span>
                  <span className="text-[11px] text-zinc-500">{group.items.length}</span>
                </div>

                <div className="space-y-2">
                  {group.items.map((iss) => {
                    const col = iss.column_id ? columnsById.get(iss.column_id) : undefined;
                    const isActive = activeIssueId === iss.id;
                    const snippets = summarizeDetails(iss.details_json);

                    return (
                      <div
                        key={iss.id}
                        className={`rounded-xl border p-3 transition-all ${
                          isActive
                            ? "border-indigo-500 bg-indigo-500/15 shadow-lg shadow-indigo-500/10"
                            : "border-zinc-800/80 bg-zinc-950/60 hover:border-zinc-700 hover:bg-zinc-900/90"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => onSelectIssue(isActive ? null : iss)}
                          className="w-full text-left"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span
                              className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${meta.badge}`}
                            >
                              {iss.type.replaceAll("_", " ")}
                            </span>
                            <span className="shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300">
                              {iss.affected_count} rows
                            </span>
                          </div>

                          {col && (
                            <div className="mt-2 inline-flex items-center rounded-md border border-zinc-800 bg-zinc-900 px-2 py-0.5 text-[11px] font-medium text-indigo-300">
                              Col: {col.name}
                            </div>
                          )}

                          <p className="mt-1.5 text-xs leading-relaxed text-zinc-200">
                            {iss.description}
                          </p>

                          {snippets.length > 0 && (
                            <div className="mt-2 space-y-1 rounded-lg bg-zinc-900/90 px-2.5 py-1.5 font-mono text-[10px] text-zinc-400">
                              {snippets.map((s, idx) => (
                                <p key={idx} className="truncate">
                                  {s}
                                </p>
                              ))}
                            </div>
                          )}
                        </button>

                        <div className="mt-2.5 flex items-center justify-between border-t border-zinc-800/60 pt-2 text-[11px]">
                          <button
                            type="button"
                            onClick={() => onSelectIssue(isActive ? null : iss)}
                            className={`font-semibold transition-colors ${
                              isActive
                                ? "text-indigo-300 hover:text-white"
                                : "text-zinc-400 hover:text-indigo-300"
                            }`}
                          >
                            {isActive ? "Showing affected rows ×" : "Highlight rows →"}
                          </button>

                          {col && (
                            <button
                              type="button"
                              onClick={() => onInspectColumn(col.id)}
                              className="inline-flex items-center space-x-1 text-zinc-400 hover:text-white transition-colors"
                            >
                              <Eye className="h-3 w-3" />
                              <span>Profile</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
