"use client";

import React, { useMemo, useRef, useState } from "react";
import {
  ColumnDef,
  columnResizingFeature,
  columnSizingFeature,
  ColumnSizingState,
  createColumnHelper,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { DatasetColumn, DatasetIssue, RowItem } from "@/lib/api";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Loader2,
  Table2,
} from "lucide-react";

const gridFeatures = tableFeatures({
  columnSizingFeature,
  columnResizingFeature,
});

const columnHelper = createColumnHelper<typeof gridFeatures, RowItem>();

interface DatasetGridProps {
  columns: DatasetColumn[];
  rows: RowItem[];
  issues: DatasetIssue[];
  activeIssue: DatasetIssue | null;
  selectedColumnId: string | null;
  sortCol: string | null;
  sortDir: "asc" | "desc";
  totalCount: number;
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  onSelectColumn: (col: DatasetColumn) => void;
  onToggleSort: (colName: string) => void;
  onLoadMore: () => void;
  onRetry: () => void;
}

function getSeverityCellClasses(severity: string, focused: boolean): string {
  if (focused) {
    switch (severity) {
      case "critical":
        return "bg-rose-500/25 text-rose-100 ring-1 ring-inset ring-rose-400/60";
      case "high":
        return "bg-orange-500/25 text-orange-100 ring-1 ring-inset ring-orange-400/60";
      case "medium":
        return "bg-amber-500/25 text-amber-100 ring-1 ring-inset ring-amber-400/60";
      default:
        return "bg-sky-500/25 text-sky-100 ring-1 ring-inset ring-sky-400/60";
    }
  }
  switch (severity) {
    case "critical":
      return "bg-rose-500/12 text-rose-200 border-b border-rose-500/20";
    case "high":
      return "bg-orange-500/12 text-orange-200 border-b border-orange-500/20";
    case "medium":
      return "bg-amber-500/10 text-amber-200 border-b border-amber-500/20";
    default:
      return "bg-sky-500/10 text-sky-200 border-b border-sky-500/20";
  }
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

export function DatasetGrid({
  columns,
  rows,
  issues,
  activeIssue,
  selectedColumnId,
  sortCol,
  sortDir,
  totalCount,
  hasMore,
  loading,
  loadingMore,
  error,
  onSelectColumn,
  onToggleSort,
  onLoadMore,
  onRetry,
}: DatasetGridProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});

  const columnsById = useMemo(() => {
    const map = new Map<string, DatasetColumn>();
    columns.forEach((c) => map.set(c.id, c));
    return map;
  }, [columns]);

  // Precompute cell-level and row-level highlights for O(1) lookup per cell render
  const { cellIssueMap, rowIssueMap, columnIssueCounts } = useMemo(() => {
    const cMap = new Map<string, { severity: string; reasons: string[] }>();
    const rMap = new Map<string, { severity: string; reasons: string[] }>();
    const colCounts = new Map<string, number>();

    const sourceIssues = activeIssue ? [activeIssue] : issues;

    for (const iss of sourceIssues) {
      if (iss.column_id) {
        colCounts.set(iss.column_id, (colCounts.get(iss.column_id) || 0) + 1);
      }
      const rowIds = iss.row_ids || [];
      const col = iss.column_id ? columnsById.get(iss.column_id) : undefined;
      const rank = SEVERITY_RANK[iss.severity] || 0;

      if (col) {
        for (const rId of rowIds) {
          const key = `${rId}::${col.name}`;
          const existing = cMap.get(key);
          if (!existing || rank > (SEVERITY_RANK[existing.severity] || 0)) {
            cMap.set(key, {
              severity: iss.severity,
              reasons: existing ? [...existing.reasons, iss.description] : [iss.description],
            });
          } else {
            existing.reasons.push(iss.description);
          }
        }
      } else {
        for (const rId of rowIds) {
          const existing = rMap.get(rId);
          if (!existing || rank > (SEVERITY_RANK[existing.severity] || 0)) {
            rMap.set(rId, {
              severity: iss.severity,
              reasons: existing ? [...existing.reasons, iss.description] : [iss.description],
            });
          } else {
            existing.reasons.push(iss.description);
          }
        }
      }
    }

    return {
      cellIssueMap: cMap,
      rowIssueMap: rMap,
      columnIssueCounts: colCounts,
    };
  }, [issues, activeIssue, columnsById]);

  const tableColumns = useMemo<ColumnDef<typeof gridFeatures, RowItem, unknown>[]>(() => {
    const indexCol = columnHelper.display({
      id: "__row_index__",
      header: () => (
        <div className="flex items-center justify-center text-[11px] font-semibold text-zinc-500">
          #
        </div>
      ),
      size: 64,
      minSize: 50,
      maxSize: 100,
      enableResizing: true,
      cell: ({ row }) => (
        <div className="text-center font-mono text-[11px] text-zinc-500 select-none">
          {row.original.row_index + 1}
        </div>
      ),
    });

    const dataCols = columns.map((col) =>
      columnHelper.accessor((row) => row.values[col.name], {
        id: col.name,
        size: 190,
        minSize: 110,
        maxSize: 520,
        enableResizing: true,
        header: () => {
          const isSelected = selectedColumnId === col.id;
          const isSorted = sortCol === col.name;
          const colIssuesCount = columnIssueCounts.get(col.id) || 0;

          return (
            <div className="flex w-full items-center justify-between gap-1.5 pr-1">
              <button
                type="button"
                onClick={() => onSelectColumn(col)}
                title={`Click to view column profile for ${col.name}`}
                className="group flex min-w-0 flex-1 flex-col text-left"
              >
                <div className="flex items-center space-x-1.5">
                  <span
                    className={`truncate text-xs font-semibold transition-colors ${
                      isSelected
                        ? "text-indigo-300"
                        : "text-zinc-100 group-hover:text-indigo-300"
                    }`}
                  >
                    {col.name}
                  </span>
                  {colIssuesCount > 0 && (
                    <span
                      className="h-2 w-2 shrink-0 rounded-full bg-amber-400"
                      title={`${colIssuesCount} issue(s) on this column`}
                    />
                  )}
                </div>
                <span className="truncate text-[10px] font-medium text-zinc-500">
                  {col.inferred_type || "raw"}
                  {col.semantic_hint ? ` • ${col.semantic_hint}` : ""}
                </span>
              </button>

              <button
                type="button"
                onClick={() => onToggleSort(col.name)}
                title={`Sort by ${col.name}`}
                className={`shrink-0 rounded p-1 transition-colors ${
                  isSorted
                    ? "bg-indigo-500/20 text-indigo-300"
                    : "text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
                aria-label={`Sort by ${col.name}`}
              >
                {isSorted ? (
                  sortDir === "asc" ? (
                    <ArrowUp className="h-3.5 w-3.5" />
                  ) : (
                    <ArrowDown className="h-3.5 w-3.5" />
                  )
                ) : (
                  <ArrowUpDown className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          );
        },
        cell: ({ row }) => {
          const rawVal = row.original.values[col.name];
          const strVal = rawVal === null || rawVal === undefined ? "" : String(rawVal);
          const cellAlert = cellIssueMap.get(`${row.original.id}::${col.name}`);
          const rowAlert = rowIssueMap.get(row.original.id);
          const alert = cellAlert || rowAlert;
          const isFocusedIssueMatch = Boolean(activeIssue && alert);

          return (
            <div
              title={alert ? alert.reasons.join(" | ") : strVal || "(empty)"}
              className={`flex h-full w-full items-center truncate px-3 py-1.5 font-mono text-xs ${
                alert
                  ? getSeverityCellClasses(alert.severity, isFocusedIssueMatch)
                  : strVal === ""
                  ? "italic text-zinc-600"
                  : "text-zinc-200"
              }`}
            >
              {strVal === "" ? "null" : strVal}
            </div>
          );
        },
      })
    );

    return columnHelper.columns([indexCol, ...dataCols]);
  }, [
    columns,
    selectedColumnId,
    sortCol,
    sortDir,
    columnIssueCounts,
    cellIssueMap,
    rowIssueMap,
    activeIssue,
    onSelectColumn,
    onToggleSort,
  ]);

  const table = useTable({
    features: gridFeatures,
    data: rows,
    columns: tableColumns,
    state: { columnSizing },
    onColumnSizingChange: setColumnSizing,
    columnResizeMode: "onChange",
  });

  const tableRows = table.getRowModel().rows;

  const rowVirtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 38,
    getItemKey: (index) => tableRows[index]?.id ?? index,
    overscan: 15,
  });

  const virtualRows = rowVirtualizer.getVirtualItems();
  const totalTableWidth = table.getTotalSize();

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (!hasMore || loadingMore || loading) return;
    const el = e.currentTarget;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 320) {
      onLoadMore();
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 p-12 text-xs text-zinc-400">
        <Loader2 className="mb-3 h-7 w-7 animate-spin text-indigo-500" />
        <p>Loading dataset rows...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 p-12 text-center">
        <AlertCircle className="mb-3 h-8 w-8 text-rose-400" />
        <p className="text-sm font-semibold text-white">Could not load rows</p>
        <p className="mt-1 max-w-md text-xs text-rose-300">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-xl bg-zinc-800 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-zinc-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 p-12 text-center">
        <Table2 className="mb-3 h-8 w-8 text-zinc-600" />
        <p className="text-sm font-semibold text-white">No rows match the current view</p>
        <p className="mt-1 max-w-md text-xs text-zinc-400">
          Try clearing the search filter or issue focus to see all rows.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-zinc-950">
      {/* Scrollable Virtualized Container */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="relative flex-1 overflow-auto"
      >
        <div style={{ width: `${totalTableWidth}px`, minWidth: "100%" }}>
          {/* Sticky Table Header */}
          <div className="sticky top-0 z-20 flex border-b border-zinc-800 bg-zinc-900/95 backdrop-blur-md">
            {table.getHeaderGroups().map((headerGroup) =>
              headerGroup.headers.map((header) => {
                const isSelectedCol =
                  columns.find((c) => c.name === header.column.id)?.id === selectedColumnId;
                return (
                  <div
                    key={header.id}
                    style={{ width: header.getSize() }}
                    className={`relative flex shrink-0 select-none items-center border-r border-zinc-800/80 px-3 py-2.5 ${
                      isSelectedCol ? "bg-indigo-500/10" : ""
                    }`}
                  >
                    {header.isPlaceholder ? null : <table.FlexRender header={header} />}

                    {header.column.getCanResize() && (
                      <div
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        className={`absolute right-0 top-0 h-full w-1.5 cursor-col-resize select-none touch-none transition-colors hover:bg-indigo-500 ${
                          header.column.getIsResizing() ? "bg-indigo-400" : ""
                        }`}
                      />
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Virtualized Rows Body */}
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              position: "relative",
              width: "100%",
            }}
          >
            {virtualRows.map((virtualRow) => {
              const row = tableRows[virtualRow.index];
              const rowAlert = rowIssueMap.get(row.original.id);

              return (
                <div
                  key={row.id}
                  data-index={virtualRow.index}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  className={`flex border-b border-zinc-800/50 transition-colors ${
                    rowAlert
                      ? "bg-amber-500/5 hover:bg-amber-500/10"
                      : virtualRow.index % 2 === 0
                      ? "bg-zinc-950 hover:bg-zinc-900/70"
                      : "bg-zinc-900/25 hover:bg-zinc-900/70"
                  }`}
                >
                  {row.getAllCells().map((cell) => {
                    const isSelectedCol =
                      columns.find((c) => c.name === cell.column.id)?.id === selectedColumnId;
                    return (
                      <div
                        key={cell.id}
                        style={{ width: cell.column.getSize() }}
                        className={`flex shrink-0 items-center overflow-hidden border-r border-zinc-800/40 ${
                          isSelectedCol ? "bg-indigo-500/5" : ""
                        }`}
                      >
                        <table.FlexRender cell={cell} />
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom Status Strip */}
      <div className="flex items-center justify-between border-t border-zinc-800 bg-zinc-900/80 px-4 py-2 text-[11px] text-zinc-400">
        <div>
          Showing <strong className="text-zinc-200">{rows.length.toLocaleString()}</strong> of{" "}
          <strong className="text-zinc-200">{totalCount.toLocaleString()}</strong> rows (read-only raw/versioned view)
        </div>

        <div className="flex items-center space-x-3">
          {loadingMore ? (
            <span className="inline-flex items-center space-x-1.5 text-indigo-300">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Loading more rows...</span>
            </span>
          ) : hasMore ? (
            <button
              type="button"
              onClick={onLoadMore}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-2.5 py-1 font-semibold text-zinc-200 transition-colors hover:bg-zinc-700"
            >
              Load next page
            </button>
          ) : (
            <span className="text-zinc-500">All matching rows loaded</span>
          )}
        </div>
      </div>
    </div>
  );
}
