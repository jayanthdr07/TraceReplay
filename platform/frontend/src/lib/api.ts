import {
  AnalyticsOverview,
  HealthResponse,
  Interaction,
  Project,
  ProjectCreate,
  SessionFilterParams,
  TestSession,
  TestSessionCreate,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      cache: "no-store", // Always fetch fresh data for real-time monitoring
    });

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }
      throw new ApiError(response.status, response.statusText, errorBody);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // Network failure / Server offline
    throw new Error(
      `Failed to connect to TraceReplay Platform API at ${url}. Is the backend running on port 8000? Details: ${
        (error as Error).message
      }`
    );
  }
}

export const api = {
  // System Health
  getHealth: async (): Promise<HealthResponse> => {
    return request<HealthResponse>("/health");
  },

  // Projects
  getProjects: async (): Promise<Project[]> => {
    return request<Project[]>("/projects");
  },

  getProject: async (projectId: string): Promise<Project> => {
    return request<Project>(`/projects/${projectId}`);
  },

  createProject: async (payload: ProjectCreate): Promise<Project> => {
    return request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Sessions
  getSessions: async (params: SessionFilterParams = {}): Promise<TestSession[]> => {
    const searchParams = new URLSearchParams();
    if (params.project_id) searchParams.append("project_id", params.project_id);
    if (params.mode) searchParams.append("mode", params.mode);
    if (params.limit) searchParams.append("limit", params.limit.toString());
    if (params.offset) searchParams.append("offset", params.offset.toString());

    const qs = searchParams.toString();
    return request<TestSession[]>(`/sessions${qs ? `?${qs}` : ""}`);
  },

  getSession: async (sessionId: string): Promise<TestSession> => {
    return request<TestSession>(`/sessions/${sessionId}`);
  },

  createSession: async (payload: TestSessionCreate): Promise<TestSession> => {
    return request<TestSession>("/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Interactions (Waterfall steps & tool calls)
  getInteractions: async (sessionId: string): Promise<Interaction[]> => {
    return request<Interaction[]>(`/interactions?session_id=${sessionId}`);
  },

  getInteraction: async (interactionId: string): Promise<Interaction> => {
    return request<Interaction>(`/interactions/${interactionId}`);
  },

  // Analytics Overview
  getAnalyticsOverview: async (projectId?: string): Promise<AnalyticsOverview> => {
    const qs = projectId ? `?project_id=${projectId}` : "";
    return request<AnalyticsOverview>(`/analytics/overview${qs}`);
  },
};
