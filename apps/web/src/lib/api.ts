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
  completeness_pct?: number;
  profiled_at?: string;
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
    count?: number;
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
  dates?: {
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

  const res = await fetch(url, { ...options, headers });
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
};
