"use client";

import React, { useState } from "react";
import { api, Dataset, ReportDetail, ReportTemplate } from "@/lib/api";
import { AlertCircle, BarChart3, Loader2, Sparkles, X } from "lucide-react";

interface GenerateReportModalProps {
  datasets: Dataset[];
  initialDatasetId?: string;
  onCreated: (report: ReportDetail) => void;
  onClose: () => void;
}

const TEMPLATES: Array<{ id: ReportTemplate; name: string; desc: string }> = [
  {
    id: "auto",
    name: "Auto-Recommend (Smart Template)",
    desc: "Automatically picks KPIs, time trends, breakdowns, and narrative based on detected schema.",
  },
  {
    id: "executive_sales",
    name: "Executive Sales & Revenue Brief",
    desc: "Monetary totals, trend performance, regional/category share, and top customer/product summary.",
  },
  {
    id: "survey_insights",
    name: "Survey & Feedback Insights",
    desc: "Department participation, recommendation mix, and safe handling of mixed rating scales.",
  },
  {
    id: "inventory_summary",
    name: "Inventory & Operations Summary",
    desc: "Stock quantities, category breakdowns, status distributions, and quality audit caveats.",
  },
  {
    id: "general_summary",
    name: "General Stakeholder Summary",
    desc: "Balanced metric overview, top categorical breakdowns, and data readiness assessment.",
  },
];

export function GenerateReportModal({
  datasets,
  initialDatasetId,
  onCreated,
  onClose,
}: GenerateReportModalProps) {
  const readyDatasets = datasets.filter((d) => d.status === "ready");
  const [selectedDatasetId, setSelectedDatasetId] = useState(
    initialDatasetId || readyDatasets[0]?.id || ""
  );
  const [template, setTemplate] = useState<ReportTemplate>("auto");
  const [customTitle, setCustomTitle] = useState("");
  const [includeNarrative, setIncludeNarrative] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDatasetId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const report = await api.analyzeDatasetToReport(selectedDatasetId, {
        template,
        title: customTitle.trim() || undefined,
        include_narrative: includeNarrative,
      });
      onCreated(report);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate stakeholder report");
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
      <div
        className="w-full max-w-lg rounded-3xl border border-zinc-800 bg-zinc-950 p-6 text-white shadow-2xl"
        role="dialog"
        aria-label="Generate Stakeholder Analysis Report"
      >
        <div className="mb-5 flex items-start justify-between border-b border-zinc-800 pb-4">
          <div className="flex items-center space-x-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500">
              <BarChart3 className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Generate Stakeholder Analysis</h2>
              <p className="text-xs text-zinc-400">
                Compute verified KPIs, interactive charts, caveats &amp; executive briefing.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-center space-x-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {readyDatasets.length === 0 ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 text-center text-xs text-zinc-400">
            Upload and finish profiling at least one dataset before generating a stakeholder report.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Source Dataset
              </label>
              <select
                required
                value={selectedDatasetId}
                onChange={(e) => setSelectedDatasetId(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                {readyDatasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name} ({ds.stats_json?.row_count ?? 0} rows ·{" "}
                    {ds.stats_json?.completeness_pct ?? 100}% complete)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Report Template
              </label>
              <div className="space-y-2">
                {TEMPLATES.map((tpl) => (
                  <label
                    key={tpl.id}
                    className={`flex cursor-pointer items-start space-x-2.5 rounded-xl border p-3 text-xs transition-colors ${
                      template === tpl.id
                        ? "border-indigo-500/60 bg-indigo-500/10"
                        : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
                    }`}
                  >
                    <input
                      type="radio"
                      name="template"
                      checked={template === tpl.id}
                      onChange={() => setTemplate(tpl.id)}
                      className="mt-0.5 accent-indigo-500"
                    />
                    <div>
                      <p className="font-semibold text-white">{tpl.name}</p>
                      <p className="mt-0.5 text-[11px] text-zinc-400">{tpl.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Custom Title (Optional)
              </label>
              <input
                type="text"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                placeholder="Auto-generated executive title if left blank"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <label className="flex cursor-pointer items-center space-x-2.5 rounded-xl border border-zinc-800 bg-zinc-900/50 px-3.5 py-2.5 text-xs">
              <input
                type="checkbox"
                checked={includeNarrative}
                onChange={(e) => setIncludeNarrative(e.target.checked)}
                className="accent-indigo-500"
              />
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span className="text-zinc-200">
                Generate executive summary briefing &amp; verify all cited numbers
              </span>
            </label>

            <div className="flex items-center justify-end space-x-3 border-t border-zinc-800 pt-4">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !selectedDatasetId}
                className="inline-flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:opacity-95 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                <span>{submitting ? "Analyzing..." : "Generate Report"}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
