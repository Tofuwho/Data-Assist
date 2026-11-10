"use client";

import React, { useState } from "react";
import {
  BlockType,
  BlockWidth,
  DatasetAnalysis,
  ReportBlockDefinition,
} from "@/lib/api";
import { PlusCircle, Save, X } from "lucide-react";

interface BlockEditorModalProps {
  existingBlock: ReportBlockDefinition | null;
  analysis: DatasetAnalysis;
  onSave: (block: ReportBlockDefinition) => void;
  onClose: () => void;
}

const BLOCK_TYPE_OPTIONS: Array<{ value: BlockType; label: string }> = [
  { value: "kpi", label: "KPI Metric Card" },
  { value: "bar_chart", label: "Bar Chart (Segment Breakdown)" },
  { value: "pie_chart", label: "Donut / Pie Chart (Share)" },
  { value: "line_chart", label: "Line Chart (Time Trend)" },
  { value: "area_chart", label: "Area Chart (Time Trend)" },
  { value: "summary_table", label: "Summary Table" },
  { value: "narrative", label: "Executive Narrative" },
  { value: "data_quality", label: "Data Quality & Caveats" },
];

export function BlockEditorModal({
  existingBlock,
  analysis,
  onSave,
  onClose,
}: BlockEditorModalProps) {
  const defaultMetric = analysis.primary_measure?.column || analysis.measures[0]?.column || "";
  const defaultMetricFmt = analysis.primary_measure?.format_style || analysis.measures[0]?.format_style || "number";
  const defaultDimension =
    analysis.dimensions[0]?.column ||
    analysis.columns.find((c) => c.inferred_type === "category")?.name ||
    analysis.columns[0]?.name ||
    "";
  const defaultDateCol =
    analysis.columns.find((c) => c.inferred_type === "date" || c.inferred_type === "datetime")?.name || "";

  const cfg = existingBlock?.config || {};

  const [blockType, setBlockType] = useState<BlockType>(
    (existingBlock?.type as BlockType) || "kpi"
  );
  const [title, setTitle] = useState(existingBlock?.title || "New KPI Metric");
  const [subtitle, setSubtitle] = useState(existingBlock?.subtitle || "");
  const [width, setWidth] = useState<BlockWidth>(
    (existingBlock?.width as BlockWidth) || (existingBlock ? "full" : "third")
  );
  const [metricColumn, setMetricColumn] = useState(
    cfg.metric_column ?? cfg.y_column ?? (existingBlock ? "" : defaultMetric)
  );
  const [secondaryMetricColumn, setSecondaryMetricColumn] = useState(
    cfg.secondary_metric_column || ""
  );
  const [dimensionColumn, setDimensionColumn] = useState(
    cfg.dimension_column ?? (existingBlock ? "" : defaultDimension)
  );
  const [xColumn, setXColumn] = useState(cfg.x_column ?? (existingBlock ? "" : defaultDateCol));
  const [aggregation, setAggregation] = useState(
    cfg.aggregation || (defaultMetric ? "sum" : "count")
  );
  const [formatStyle, setFormatStyle] = useState(
    cfg.format_style || defaultMetricFmt || "number"
  );
  const [granularity, setGranularity] = useState(cfg.granularity || "day");
  const [sortBy, setSortBy] = useState(cfg.sort_by || "value_desc");
  const [limit, setLimit] = useState<number>(cfg.limit ?? 10);

  const handleTypeChange = (nextType: BlockType) => {
    setBlockType(nextType);
    if (!existingBlock) {
      if (nextType === "kpi") {
        setWidth("third");
        setTitle(metricColumn ? `Total ${metricColumn}` : "Total Records");
      } else if (nextType === "bar_chart" || nextType === "pie_chart") {
        setWidth("half");
        setTitle(
          `${metricColumn || "Record Count"} by ${dimensionColumn || "Segment"}`
        );
      } else if (nextType === "line_chart" || nextType === "area_chart") {
        setWidth("full");
        setTitle(`${metricColumn || "Activity"} Over Time`);
      } else if (nextType === "summary_table") {
        setWidth("full");
        setTitle(`${dimensionColumn || "Segment"} Summary Table`);
      } else if (nextType === "narrative") {
        setWidth("full");
        setTitle("Executive Briefing & Key Takeaways");
      } else {
        setWidth("full");
        setTitle("Data Quality & Methodology Caveats");
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = existingBlock?.id || `blk_${blockType}_${Date.now().toString(36)}`;

    const nextConfig: Record<string, unknown> = {};
    if (blockType === "kpi") {
      nextConfig.metric_column = aggregation === "count" ? null : metricColumn || null;
      nextConfig.aggregation = metricColumn ? aggregation : "count";
      nextConfig.format_style = aggregation === "count" ? "number" : formatStyle;
    } else if (blockType === "bar_chart" || blockType === "pie_chart") {
      nextConfig.dimension_column = dimensionColumn;
      nextConfig.metric_column = aggregation === "count" ? null : metricColumn || null;
      nextConfig.aggregation = metricColumn ? aggregation : "count";
      nextConfig.format_style = aggregation === "count" ? "number" : formatStyle;
      nextConfig.limit = limit;
      nextConfig.sort_by = sortBy;
    } else if (blockType === "line_chart" || blockType === "area_chart") {
      nextConfig.x_column = xColumn;
      nextConfig.y_column = aggregation === "count" ? null : metricColumn || null;
      nextConfig.aggregation = metricColumn ? aggregation : "count";
      nextConfig.granularity = granularity;
      nextConfig.format_style = aggregation === "count" ? "number" : formatStyle;
    } else if (blockType === "summary_table") {
      nextConfig.dimension_column = dimensionColumn;
      nextConfig.metric_column = aggregation === "count" ? null : metricColumn || null;
      nextConfig.secondary_metric_column = secondaryMetricColumn || null;
      nextConfig.aggregation = metricColumn ? aggregation : "count";
      nextConfig.format_style = aggregation === "count" ? "number" : formatStyle;
      nextConfig.limit = limit;
      nextConfig.sort_by = sortBy;
    } else if (blockType === "data_quality") {
      nextConfig.show_resolved = false;
    }

    onSave({
      id,
      type: blockType,
      title: title.trim() || "Untitled Block",
      subtitle: subtitle.trim() || null,
      width,
      config: nextConfig,
      ...(blockType === "narrative" && existingBlock?.content
        ? { content: existingBlock.content }
        : {}),
    });
  };

  const needsMetric = ["kpi", "bar_chart", "pie_chart", "line_chart", "area_chart", "summary_table"].includes(blockType);
  const needsDimension = ["bar_chart", "pie_chart", "summary_table"].includes(blockType);
  const needsDateCol = ["line_chart", "area_chart"].includes(blockType);

  const dateCols = analysis.columns.filter(
    (c) => c.inferred_type === "date" || c.inferred_type === "datetime"
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
      <div
        className="w-full max-w-xl rounded-3xl border border-zinc-800 bg-zinc-950 p-6 text-white shadow-2xl"
        role="dialog"
        aria-label={existingBlock ? "Configure Report Block" : "Add Report Block"}
      >
        <div className="mb-5 flex items-center justify-between border-b border-zinc-800 pb-3.5">
          <div>
            <h2 className="text-lg font-bold text-white">
              {existingBlock ? "Configure Report Block" : "Add Stakeholder Report Block"}
            </h2>
            <p className="text-xs text-zinc-400">
              All numbers and chart segments compute server-side with full row lineage.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close block editor"
            className="rounded-xl border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Block Type
              </label>
              <select
                value={blockType}
                onChange={(e) => handleTypeChange(e.target.value as BlockType)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                {BLOCK_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Layout Width
              </label>
              <select
                value={width}
                onChange={(e) => setWidth(e.target.value as BlockWidth)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                <option value="third">One-Third (KPI Row)</option>
                <option value="half">Half Width (2-Column)</option>
                <option value="full">Full Width</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Block Title
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Subtitle / Context (Optional)
              </label>
              <input
                type="text"
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="Click bars to inspect source rows"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          {needsDimension && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Group By Dimension Column
              </label>
              <select
                required
                value={dimensionColumn}
                onChange={(e) => setDimensionColumn(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                {analysis.columns.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.inferred_type || "raw"})
                  </option>
                ))}
              </select>
            </div>
          )}

          {needsDateCol && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Date / Time Column
                </label>
                <select
                  required
                  value={xColumn}
                  onChange={(e) => setXColumn(e.target.value)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  {(dateCols.length > 0 ? dateCols : analysis.columns).map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name} ({c.inferred_type || "raw"})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Time Granularity
                </label>
                <select
                  value={granularity}
                  onChange={(e) => setGranularity(e.target.value)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="day">Daily</option>
                  <option value="week">Weekly</option>
                  <option value="month">Monthly</option>
                </select>
              </div>
            </div>
          )}

          {needsMetric && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Metric Column
                </label>
                <select
                  value={metricColumn}
                  onChange={(e) => {
                    const nextCol = e.target.value;
                    setMetricColumn(nextCol);
                    const matched = analysis.measures.find((m) => m.column === nextCol);
                    if (matched) {
                      setFormatStyle(matched.format_style);
                      if (aggregation === "count") setAggregation("sum");
                    } else if (!nextCol) {
                      setAggregation("count");
                      setFormatStyle("number");
                    }
                  }}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="">(Row Count Only)</option>
                  {analysis.columns.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name} ({c.inferred_type || "raw"})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Aggregation
                </label>
                <select
                  value={aggregation}
                  onChange={(e) => setAggregation(e.target.value)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="sum">Sum</option>
                  <option value="mean">Average (Mean)</option>
                  {blockType === "kpi" && <option value="median">Median</option>}
                  {blockType === "kpi" && <option value="min">Minimum</option>}
                  {blockType === "kpi" && <option value="max">Maximum</option>}
                  <option value="count">Row Count</option>
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Number Format
                </label>
                <select
                  value={formatStyle}
                  onChange={(e) => setFormatStyle(e.target.value)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="currency">Currency ($)</option>
                  <option value="number">Numeric (1,234)</option>
                  <option value="percent">Percentage (%)</option>
                </select>
              </div>
            </div>
          )}

          {blockType === "summary_table" && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                Secondary Metric Column (Optional)
              </label>
              <select
                value={secondaryMetricColumn}
                onChange={(e) => setSecondaryMetricColumn(e.target.value)}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
              >
                <option value="">None</option>
                {analysis.measures.map((m) => (
                  <option key={m.column} value={m.column}>
                    {m.column}
                  </option>
                ))}
              </select>
            </div>
          )}

          {needsDimension && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Sort Order
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="value_desc">Highest Value First</option>
                  <option value="value_asc">Lowest Value First</option>
                  <option value="label_asc">Alphabetical</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zinc-300">
                  Max Segments Shown
                </label>
                <input
                  type="number"
                  min={2}
                  max={50}
                  value={limit}
                  onChange={(e) => setLimit(Math.max(2, Math.min(50, Number(e.target.value) || 10)))}
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>
          )}

          <div className="flex items-center justify-end space-x-3 border-t border-zinc-800 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="inline-flex items-center space-x-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500"
            >
              {existingBlock ? <Save className="h-3.5 w-3.5" /> : <PlusCircle className="h-3.5 w-3.5" />}
              <span>{existingBlock ? "Update Block" : "Add to Report"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
