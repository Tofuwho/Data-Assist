const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  role: "admin" | "steward" | "stakeholder" | "contributor";
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Membership {
  id: string;
  user_id: string;
  workspace_id: string;
  role: string;
  user?: User;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface IssueCounts {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface DatasetStats {
  row_count?: number;
  column_count?: number;
  total_cells?: number;
  null_cells?: number;
  null_like_cells?: number;
  completeness_pct?: number;
  profiled_at?: string;
  profile_duration_ms?: number;
  duration_ms?: number;
  sheet_name?: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  status: "processing" | "ready" | "failed" | string;
  error_message: string | null;
  stats_json: DatasetStats | null;
  issue_counts: IssueCounts | null;
  created_at: string;
  updated_at: string;
}

export interface DatasetItemSummary {
  dataset_id: string;
  name: string;
  job_id: string;
}

export interface DatasetUploadResponse {
  dataset_id: string;
  job_id: string;
  name: string;
  status: string;
  datasets?: DatasetItemSummary[] | null;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "started" | "finished" | "failed" | string;
  result?: unknown;
  error?: string | null;
}

export interface TopValueItem {
  value: string;
  count: number;
}

export interface ColumnProfileStats {
  total_count?: number;
  non_null_count?: number;
  empty_count?: number;
  null_like_count?: number;
  null_count?: number;
  null_pct?: number;
  distinct_count?: number;
  inferred_type?: string;
  semantic_hint?: string | null;
  top_values?: TopValueItem[];
  format_patterns?: Record<string, number>;
  numeric?: {
    valid_count?: number;
    invalid_count?: number;
    min?: number;
    max?: number;
    mean?: number;
    median?: number;
    sum?: number;
    q1?: number;
    q3?: number;
    iqr?: number;
  } | null;
  text?: {
    min_length?: number;
    max_length?: number;
    avg_length?: number;
    whitespace_count?: number;
    whitespace_pct?: number;
    case_distribution?: Record<string, number>;
  } | null;
  date?: {
    formats?: Record<string, number>;
    ambiguous_count?: number;
    min?: string | null;
    max?: string | null;
  } | null;
}

export interface DatasetColumn {
  id: string;
  dataset_id: string;
  name: string;
  position: number;
  inferred_type: string | null;
  semantic_hint: string | null;
  stats_json: ColumnProfileStats | null;
  created_at: string;
}

export interface DatasetIssue {
  id: string;
  dataset_id: string;
  type: string;
  severity: "critical" | "high" | "medium" | "low" | string;
  column_id: string | null;
  row_ids: string[] | null;
  affected_count: number;
  status: string;
  source: string;
  assignee_id: string | null;
  description: string;
  details_json: Record<string, unknown> | null;
  created_at: string;
}

export interface RowItem {
  id: string;
  row_index: number;
  values: Record<string, unknown>;
}

export interface RowPage {
  dataset_id: string;
  version_id: string | null;
  total_count: number;
  limit: number;
  next_cursor: string | null;
  has_more: boolean;
  items: RowItem[];
}

export interface RowQueryParams {
  cursor?: string;
  limit?: number;
  sort?: string;
  sort_dir?: "asc" | "desc";
  filter?: string;
  issue_id?: string;
  version_id?: string;
}

export interface IssueQueryParams {
  severity?: string;
  type?: string;
  column_id?: string;
  status?: string;
}

export type ReportTemplate =
  | "auto"
  | "executive_sales"
  | "survey_insights"
  | "inventory_summary"
  | "general_summary";

export type ReportStatus = "draft" | "in_review" | "approved" | "published";

export type BlockType =
  | "narrative"
  | "kpi"
  | "bar_chart"
  | "line_chart"
  | "area_chart"
  | "pie_chart"
  | "summary_table"
  | "data_quality";

export type BlockWidth = "third" | "half" | "full";

export interface ReportBlockConfig {
  metric_column?: string | null;
  secondary_metric_column?: string | null;
  dimension_column?: string | null;
  x_column?: string | null;
  y_column?: string | null;
  aggregation?: string;
  format_style?: string;
  granularity?: string;
  limit?: number;
  sort_by?: string;
  filter_column?: string | null;
  filter_value?: string | null;
  show_resolved?: boolean;
}

export interface NarrativeVerification {
  verified: boolean;
  total_numbers_checked: number;
  unverified_numbers: string[];
  checked_at: string;
}

export interface NarrativeContent {
  headline: string;
  executive_summary: string;
  key_findings: string[];
  recommendations: string[];
  caveats: string[];
  provider?: string;
  model?: string;
  generated_at?: string;
  verification?: NarrativeVerification;
}

export interface ReportBlockDefinition {
  id: string;
  type: BlockType | string;
  title: string;
  subtitle?: string | null;
  width: BlockWidth | string;
  config: ReportBlockConfig;
  content?: NarrativeContent | null;
}

export interface ReportLayout {
  version: number;
  template: string;
  blocks: ReportBlockDefinition[];
}

export interface AnalysisOverview {
  row_count: number;
  column_count: number;
  null_cells: number;
  completeness_pct: number;
  open_issues_count: number;
  high_critical_issues_count: number;
  resolved_issues_count: number;
  readiness: "verified" | "needs_review" | "caution" | string;
  readiness_score: number;
}

export interface AnalysisMeasure {
  column: string;
  inferred_type: string | null;
  semantic_hint: string | null;
  format_style: string;
  valid_count: number;
  missing_count: number;
  unparseable_count: number;
  currency_notations?: string[];
  is_primary: boolean;
  sum: number;
  mean: number;
  median: number;
  min: number;
  max: number;
  q1: number;
  q3: number;
  iqr: number;
}

export interface AnalysisDimension {
  column: string;
  inferred_type: string | null;
  semantic_hint: string | null;
  distinct_count: number;
  non_null_count: number;
  missing_count: number;
  top_values: Array<{ value: string; count: number; share_pct: number }>;
}

export interface DataQualityCaveat {
  id: string;
  severity: "critical" | "high" | "medium" | "low" | string;
  category: string;
  column: string | null;
  title: string;
  message: string;
  affected_count: number;
}

export interface AnalysisColumnOption {
  name: string;
  inferred_type: string | null;
  semantic_hint: string | null;
}

export interface DatasetAnalysis {
  dataset_id: string;
  dataset_name: string;
  version_id: string;
  version_number: number;
  generated_at: string;
  overview: AnalysisOverview;
  measures: AnalysisMeasure[];
  primary_measure: AnalysisMeasure | null;
  dimensions: AnalysisDimension[];
  segment_breakdowns: Array<Record<string, unknown>>;
  time_series: Record<string, unknown> | null;
  correlations: Array<{
    column_a: string;
    column_b: string;
    pearson_r: number;
    paired_rows: number;
    strength: string;
    direction: string;
  }>;
  data_quality_caveats: DataQualityCaveat[];
  columns: AnalysisColumnOption[];
}

export interface ComputedBlock {
  id: string;
  type: BlockType | string;
  title: string;
  subtitle?: string | null;
  width: BlockWidth | string;
  config: ReportBlockConfig;
  data: Record<string, unknown> | NarrativeContent | null;
}

export interface ReportListItem {
  id: string;
  project_id: string;
  dataset_id: string;
  dataset_name: string;
  dataset_version_id: string;
  version_number: number;
  title: string;
  status: ReportStatus | string;
  template: string;
  block_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReportDetail {
  id: string;
  project_id: string;
  dataset_id: string;
  dataset_name: string;
  dataset_version_id: string;
  version_number: number;
  title: string;
  status: ReportStatus | string;
  template: string;
  layout_json: ReportLayout;
  computed_blocks: ComputedBlock[];
  analysis: DatasetAnalysis;
  created_at: string;
  updated_at: string;
}

export interface RowChangeAuditItem {
  id: string;
  column_name: string;
  before: string | null;
  after: string | null;
  source: string;
  reason: string | null;
  status: string;
  created_at: string | null;
}

export interface LineageRowItem {
  row_id: string;
  row_index: number;
  raw_values: Record<string, unknown>;
  effective_values: Record<string, unknown>;
  changed_columns: string[];
  changes: RowChangeAuditItem[];
}

export interface BlockLineageResponse {
  block_id: string;
  block_type: string;
  block_title: string;
  bucket_key: string | null;
  bucket_label: string | null;
  dataset_id: string;
  dataset_name: string;
  version_id: string;
  version_number: number;
  highlight_columns: string[];
  columns: string[];
  total_matching_rows: number;
  excluded_row_count: number;
  excluded_reasons: Record<string, number>;
  limit: number;
  offset: number;
  has_more: boolean;
  rows: LineageRowItem[];
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("cleardata_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...getAuthHeader(),
    ...((options.headers as Record<string, string> | undefined) || {}),
  };

  let res: Response;
  try {
    res = await fetch(url, { ...options, headers });
  } catch {
    throw new Error(
      `Unable to reach ClearData API at ${API_BASE}. Make sure the backend server is running.`
    );
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const errorMsg = data?.error?.message || data?.detail || `Request failed with status ${res.status}`;
    throw new Error(errorMsg);
  }

  return data as T;
}

export const api = {
  // Auth
  async register(payload: { email: string; password: string; name: string; workspace_name?: string }): Promise<AuthResponse> {
    const data = await request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (data.access_token) {
      localStorage.setItem("cleardata_token", data.access_token);
    }
    return data;
  },

  async login(payload: { email: string; password: string }): Promise<AuthResponse> {
    const data = await request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (data.access_token) {
      localStorage.setItem("cleardata_token", data.access_token);
    }
    return data;
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me");
  },

  logout(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem("cleardata_token");
    }
  },

  // Workspaces
  async getWorkspaces(): Promise<Workspace[]> {
    return request<Workspace[]>("/workspaces");
  },

  async createWorkspace(name: string): Promise<Workspace> {
    return request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  async getWorkspace(workspaceId: string): Promise<Workspace> {
    return request<Workspace>(`/workspaces/${workspaceId}`);
  },

  // Workspace Members
  async getWorkspaceMembers(workspaceId: string): Promise<Membership[]> {
    return request<Membership[]>(`/workspaces/${workspaceId}/members`);
  },

  async addWorkspaceMember(workspaceId: string, email: string, role: string): Promise<Membership> {
    return request<Membership>(`/workspaces/${workspaceId}/members`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
  },

  // Projects
  async getProjects(workspaceId: string): Promise<Project[]> {
    return request<Project[]>(`/workspaces/${workspaceId}/projects`);
  },

  async getProject(projectId: string): Promise<Project> {
    return request<Project>(`/projects/${projectId}`);
  },

  async createProject(workspaceId: string, name: string): Promise<Project> {
    return request<Project>(`/workspaces/${workspaceId}/projects`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  // Datasets & Jobs
  async listDatasets(projectId: string): Promise<Dataset[]> {
    return request<Dataset[]>(`/projects/${projectId}/datasets`);
  },

  async uploadDataset(
    projectId: string,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<DatasetUploadResponse> {
    const url = `${API_BASE}/projects/${projectId}/datasets`;
    const formData = new FormData();
    formData.append("file", file);

    return new Promise<DatasetUploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);

      const authHeaders = getAuthHeader();
      Object.entries(authHeaders).forEach(([k, v]) => {
        xhr.setRequestHeader(k, v);
      });

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && onProgress) {
          const pct = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
          onProgress(pct);
        }
      };

      xhr.onload = () => {
        let parsed: Record<string, unknown> | null = null;
        try {
          parsed = xhr.responseText ? (JSON.parse(xhr.responseText) as Record<string, unknown>) : null;
        } catch {
          parsed = null;
        }

        if (xhr.status >= 200 && xhr.status < 300 && parsed) {
          resolve(parsed as unknown as DatasetUploadResponse);
        } else {
          const errObj = parsed?.error as { message?: string } | undefined;
          const detail = parsed?.detail as string | undefined;
          reject(new Error(errObj?.message || detail || `Upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error("Network error while uploading dataset."));
      };

      xhr.send(formData);
    });
  },

  async getJobStatus(jobId: string): Promise<JobStatus> {
    return request<JobStatus>(`/jobs/${jobId}`);
  },

  async getDataset(datasetId: string): Promise<Dataset> {
    return request<Dataset>(`/datasets/${datasetId}`);
  },

  async getDatasetColumns(datasetId: string): Promise<DatasetColumn[]> {
    return request<DatasetColumn[]>(`/datasets/${datasetId}/columns`);
  },

  async getDatasetRows(datasetId: string, params: RowQueryParams = {}): Promise<RowPage> {
    const qs = new URLSearchParams();
    if (params.cursor !== undefined) qs.set("cursor", params.cursor);
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.sort) qs.set("sort", params.sort);
    if (params.sort_dir) qs.set("sort_dir", params.sort_dir);
    if (params.filter) qs.set("filter", params.filter);
    if (params.issue_id) qs.set("issue_id", params.issue_id);
    if (params.version_id) qs.set("version_id", params.version_id);
    const query = qs.toString();
    return request<RowPage>(`/datasets/${datasetId}/rows${query ? `?${query}` : ""}`);
  },

  async getDatasetIssues(datasetId: string, params: IssueQueryParams = {}): Promise<DatasetIssue[]> {
    const qs = new URLSearchParams();
    if (params.severity) qs.set("severity", params.severity);
    if (params.type) qs.set("type", params.type);
    if (params.column_id) qs.set("column_id", params.column_id);
    if (params.status) qs.set("status", params.status);
    const query = qs.toString();
    return request<DatasetIssue[]>(`/datasets/${datasetId}/issues${query ? `?${query}` : ""}`);
  },

  async reprofileDataset(datasetId: string): Promise<JobStatus> {
    return request<JobStatus>(`/datasets/${datasetId}/profile`, {
      method: "POST",
    });
  },

  // Stakeholder Analysis & Reports
  async getDatasetAnalysis(datasetId: string, versionId?: string): Promise<DatasetAnalysis> {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
    return request<DatasetAnalysis>(`/datasets/${datasetId}/analysis${query}`);
  },

  async analyzeDatasetToReport(
    datasetId: string,
    payload: {
      version_id?: string;
      template?: ReportTemplate;
      title?: string;
      include_narrative?: boolean;
      llm_provider?: string;
    } = {}
  ): Promise<ReportDetail> {
    return request<ReportDetail>(`/datasets/${datasetId}/analyze`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listProjectReports(projectId: string): Promise<ReportListItem[]> {
    return request<ReportListItem[]>(`/projects/${projectId}/reports`);
  },

  async createReport(
    projectId: string,
    payload: {
      dataset_id: string;
      dataset_version_id?: string;
      title?: string;
      template?: ReportTemplate;
      layout_json?: ReportLayout;
      include_narrative?: boolean;
    }
  ): Promise<ReportDetail> {
    return request<ReportDetail>(`/projects/${projectId}/reports`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getReport(reportId: string): Promise<ReportDetail> {
    return request<ReportDetail>(`/reports/${reportId}`);
  },

  async updateReport(
    reportId: string,
    payload: {
      title?: string;
      status?: ReportStatus;
      layout_json?: ReportLayout;
    }
  ): Promise<ReportDetail> {
    return request<ReportDetail>(`/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async deleteReport(reportId: string): Promise<void> {
    return request<void>(`/reports/${reportId}`, {
      method: "DELETE",
    });
  },

  async computeReport(reportId: string): Promise<ReportDetail> {
    return request<ReportDetail>(`/reports/${reportId}/compute`, {
      method: "POST",
    });
  },

  async generateReportNarrative(
    reportId: string,
    payload: { block_id?: string; llm_provider?: string } = {}
  ): Promise<ReportDetail> {
    return request<ReportDetail>(`/reports/${reportId}/narrative`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getBlockLineage(
    reportId: string,
    blockId: string,
    params: { bucket_key?: string; limit?: number; offset?: number } = {}
  ): Promise<BlockLineageResponse> {
    const qs = new URLSearchParams();
    if (params.bucket_key !== undefined && params.bucket_key !== null) {
      qs.set("bucket_key", params.bucket_key);
    }
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return request<BlockLineageResponse>(
      `/reports/${reportId}/blocks/${blockId}/lineage${query ? `?${query}` : ""}`
    );
  },

  async exportReportWorkbook(reportId: string, fallbackTitle = "stakeholder_report"): Promise<void> {
    const res = await fetch(`${API_BASE}/reports/${reportId}/export?format=xlsx`, {
      headers: { ...getAuthHeader() },
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => null);
      throw new Error(errJson?.error?.message || `Export failed with status ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] || `${fallbackTitle.replace(/[^a-z0-9._-]+/gi, "_")}.xlsx`;

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};
