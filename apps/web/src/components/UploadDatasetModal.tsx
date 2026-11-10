"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  api,
  Dataset,
  DatasetUploadResponse,
  JobStatus,
} from "@/lib/api";
import {
  UploadCloud,
  FileSpreadsheet,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

const ALLOWED_EXTENSIONS = [".csv", ".tsv", ".xlsx"];
const MAX_SIZE_MB = 25;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

interface TrackedDatasetJob {
  datasetId: string;
  name: string;
  jobId: string;
  jobStatus: string;
  datasetStatus: string;
  error: string | null;
}

interface UploadDatasetModalProps {
  isOpen: boolean;
  projectId: string;
  onClose: () => void;
  onUploadCompleted: (datasets: Dataset[]) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function UploadDatasetModal({
  isOpen,
  projectId,
  onClose,
  onUploadCompleted,
}: UploadDatasetModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [phase, setPhase] = useState<"idle" | "uploading" | "polling" | "done" | "error">("idle");
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadResponse, setUploadResponse] = useState<DatasetUploadResponse | null>(null);
  const [trackedJobs, setTrackedJobs] = useState<TrackedDatasetJob[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const resetState = () => {
    setDragActive(false);
    setSelectedFile(null);
    setValidationError(null);
    setPhase("idle");
    setUploadPercent(0);
    setUploadResponse(null);
    setTrackedJobs([]);
    setErrorMessage(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  useEffect(() => {
    if (!isOpen || phase !== "polling" || trackedJobs.length === 0) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const pollOnce = async () => {
      try {
        const updated = await Promise.all(
          trackedJobs.map(async (item) => {
            if (item.datasetStatus === "ready" || item.jobStatus === "failed" || item.datasetStatus === "failed") {
              return item;
            }

            let nextJobId = item.jobId;
            let jobRes: JobStatus | null = null;
            try {
              jobRes = await api.getJobStatus(item.jobId);
            } catch {
              jobRes = null;
            }

            // Follow chained profiling/detection jobs when queue workers run asynchronously
            if (jobRes?.status === "finished" && jobRes.result && typeof jobRes.result === "object") {
              const resObj = jobRes.result as Record<string, unknown>;
              if (typeof resObj.profile_job_id === "string" && resObj.profile_job_id !== item.jobId) {
                nextJobId = resObj.profile_job_id;
              } else if (typeof resObj.detection_job_id === "string" && resObj.detection_job_id !== item.jobId) {
                nextJobId = resObj.detection_job_id;
              }
            }

            let ds: Dataset | null = null;
            try {
              ds = await api.getDataset(item.datasetId);
            } catch {
              ds = null;
            }

            const jobFailed = jobRes?.status === "failed";
            const dsFailed = ds?.status === "failed";
            const dsReady = ds?.status === "ready";
            const profiledDone = Boolean(ds?.stats_json?.profiled_at);

            const isTerminalReady =
              dsReady &&
              (profiledDone ||
                (jobRes?.status === "finished" && nextJobId === item.jobId));

            const err =
              ds?.error_message ||
              jobRes?.error ||
              (jobFailed || dsFailed ? "Dataset processing failed." : null);

            return {
              ...item,
              jobId: nextJobId,
              jobStatus: jobFailed ? "failed" : isTerminalReady ? "finished" : jobRes?.status || item.jobStatus,
              datasetStatus: dsFailed ? "failed" : isTerminalReady ? "ready" : ds?.status || item.datasetStatus,
              error: err,
            };
          })
        );

        if (cancelled) return;
        setTrackedJobs(updated);

        const anyFailed = updated.some((t) => t.jobStatus === "failed" || t.datasetStatus === "failed");
        const allTerminal = updated.every(
          (t) =>
            (t.datasetStatus === "ready" && t.jobStatus === "finished") ||
            t.jobStatus === "failed" ||
            t.datasetStatus === "failed"
        );

        if (allTerminal) {
          if (anyFailed) {
            const firstErr = updated.find((t) => t.error)?.error || "One or more datasets failed to process.";
            setErrorMessage(firstErr);
            setPhase("error");
          } else {
            setPhase("done");
          }
          try {
            const freshList = await api.listDatasets(projectId);
            if (!cancelled) {
              onUploadCompleted(freshList);
            }
          } catch {
            // Ignore list refresh error here; parent reloads on demand
          }
          return;
        }

        timer = setTimeout(pollOnce, 750);
      } catch (err: unknown) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : "Failed to poll upload job status.");
          setPhase("error");
        }
      }
    };

    pollOnce();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [isOpen, phase, trackedJobs, projectId, onUploadCompleted]);

  if (!isOpen) return null;

  const validateAndSelect = (file: File | undefined | null) => {
    setValidationError(null);
    setErrorMessage(null);
    if (!file) return;

    const lower = file.name.toLowerCase();
    const hasAllowedExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
    if (!hasAllowedExt) {
      setSelectedFile(null);
      setValidationError(`Unsupported file type. Please upload ${ALLOWED_EXTENSIONS.join(", ")}.`);
      return;
    }

    if (file.size === 0) {
      setSelectedFile(null);
      setValidationError("The selected file is empty (0 bytes).");
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setSelectedFile(null);
      setValidationError(`File exceeds ${MAX_SIZE_MB} MB limit (${formatFileSize(file.size)}).`);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (phase === "uploading" || phase === "polling") return;
    validateAndSelect(e.dataTransfer.files?.[0]);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setPhase("uploading");
    setUploadPercent(0);
    setErrorMessage(null);

    try {
      const res = await api.uploadDataset(projectId, selectedFile, setUploadPercent);
      setUploadPercent(100);
      setUploadResponse(res);

      const targets =
        res.datasets && res.datasets.length > 0
          ? res.datasets
          : [{ dataset_id: res.dataset_id, name: res.name, job_id: res.job_id }];

      setTrackedJobs(
        targets.map((t) => ({
          datasetId: t.dataset_id,
          name: t.name,
          jobId: t.job_id,
          jobStatus: "queued",
          datasetStatus: "processing",
          error: null,
        }))
      );
      setPhase("polling");
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Upload failed.");
      setPhase("error");
    }
  };

  const isBusy = phase === "uploading" || phase === "polling";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl ring-1 ring-white/10 animate-in zoom-in-95 duration-200">
        <button
          type="button"
          onClick={handleClose}
          disabled={phase === "uploading"}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:opacity-40"
          aria-label="Close upload dialog"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-5 flex items-center space-x-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/20 bg-indigo-500/10 text-indigo-400">
            <UploadCloud className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Upload Raw Dataset</h3>
            <p className="text-xs text-zinc-400">
              Original bytes stay immutable. CSV, TSV, and multi-sheet Excel (.xlsx) up to {MAX_SIZE_MB} MB.
            </p>
          </div>
        </div>

        {(validationError || errorMessage) && (
          <div className="mb-4 flex items-start space-x-2.5 rounded-xl border border-rose-500/25 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <div className="space-y-1">
              <p className="font-semibold text-rose-200">Upload / Processing Error</p>
              <p className="text-rose-300/90">{validationError || errorMessage}</p>
            </div>
          </div>
        )}

        {phase === "idle" || (phase === "error" && trackedJobs.length === 0) ? (
          <>
            <div
              onDragEnter={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(false);
              }}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
                dragActive
                  ? "border-indigo-400 bg-indigo-500/10"
                  : selectedFile
                  ? "border-emerald-500/40 bg-emerald-500/5"
                  : "border-zinc-700/80 bg-zinc-950/60 hover:border-zinc-600 hover:bg-zinc-950"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.tsv,.xlsx"
                className="hidden"
                onChange={(e) => validateAndSelect(e.target.files?.[0])}
              />

              {selectedFile ? (
                <div className="flex flex-col items-center space-y-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    <FileSpreadsheet className="h-6 w-6" />
                  </div>
                  <p className="text-sm font-semibold text-white">{selectedFile.name}</p>
                  <p className="text-xs text-zinc-400">{formatFileSize(selectedFile.size)} • Ready to upload</p>
                  <span className="mt-1 text-[11px] font-medium text-indigo-400 hover:underline">
                    Click or drop another file to replace
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center space-y-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-400">
                    <UploadCloud className="h-6 w-6" />
                  </div>
                  <p className="text-sm font-semibold text-white">Drag &amp; drop your file here</p>
                  <p className="text-xs text-zinc-400">or click to browse (.csv, .tsv, .xlsx)</p>
                </div>
              )}
            </div>

            <div className="mt-6 flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-xl px-4 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedFile}
                onClick={handleUpload}
                className="flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <UploadCloud className="h-4 w-4" />
                <span>Upload &amp; Profile</span>
              </button>
            </div>
          </>
        ) : (
          <div className="space-y-4">
            {/* Upload Progress Bar */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-medium text-zinc-200 truncate pr-4">
                  {selectedFile?.name || uploadResponse?.name}
                </span>
                <span className="font-mono text-indigo-400">
                  {phase === "uploading" ? `${uploadPercent}%` : "Uploaded"}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={`h-full transition-all duration-300 ${
                    phase === "error"
                      ? "bg-rose-500"
                      : phase === "done"
                      ? "bg-emerald-500"
                      : "bg-gradient-to-r from-indigo-500 to-violet-500"
                  }`}
                  style={{ width: `${phase === "uploading" ? uploadPercent : 100}%` }}
                />
              </div>
            </div>

            {/* Job Polling List */}
            {trackedJobs.length > 0 && (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  Ingestion, Profiling &amp; Issue Detection
                </p>
                {trackedJobs.map((job) => {
                  const isFailed = job.jobStatus === "failed" || job.datasetStatus === "failed";
                  const isDone = job.datasetStatus === "ready" && job.jobStatus === "finished";
                  return (
                    <div
                      key={job.datasetId}
                      className="flex items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-3.5 py-2.5 text-xs"
                    >
                      <div className="min-w-0 pr-3">
                        <p className="truncate font-medium text-white">{job.name}</p>
                        {job.error && (
                          <p className="mt-0.5 text-[11px] text-rose-400">{job.error}</p>
                        )}
                      </div>
                      <div className="shrink-0">
                        {isFailed ? (
                          <span className="inline-flex items-center space-x-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-300">
                            <AlertCircle className="h-3.5 w-3.5" />
                            <span>Failed</span>
                          </span>
                        ) : isDone ? (
                          <span className="inline-flex items-center space-x-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>Ready</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            <span>Processing</span>
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex items-center justify-end space-x-3 pt-2">
              {phase === "error" && (
                <button
                  type="button"
                  onClick={() => {
                    setPhase("idle");
                    setTrackedJobs([]);
                    setErrorMessage(null);
                  }}
                  className="flex items-center space-x-1.5 rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-2 text-xs font-semibold text-white hover:bg-zinc-700 transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>Try Another File</span>
                </button>
              )}
              <button
                type="button"
                disabled={isBusy}
                onClick={handleClose}
                className="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors disabled:opacity-40"
              >
                {phase === "done" ? "Done" : isBusy ? "Processing..." : "Close"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
