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

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("cleardata_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...getAuthHeader(),
    ...options.headers,
  };

  const res = await fetch(url, { ...options, headers });
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

  async createProject(workspaceId: string, name: string): Promise<Project> {
    return request<Project>(`/workspaces/${workspaceId}/projects`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },
};
