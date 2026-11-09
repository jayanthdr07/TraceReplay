export type SessionStatus = "passed" | "failed" | "recorded";
export type SessionMode = "record" | "replay" | "auto" | "passthrough";


export interface DatabaseHealth {
  mode: "cloud" | "local";
  status: "connected" | "disconnected" | "healthy";
  provider: "supabase_postgresql" | "filesystem";
  url?: string;
  query_success: boolean;
  rows_returned?: number;
  discovered_fixtures_count?: number;
  fixtures_directory?: string;
}


export interface HealthResponse {
  status: "healthy" | "degraded";
  project: string;
  version: string;
  environment: "development" | "production" | "local" | "testing";
  database: DatabaseHealth;
}

export interface Project {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  description: string;
  api_key_hash?: string | null;
  created_at: string;
  updated_at?: string | null;
}


export interface ProjectCreate {
  name: string;
  slug: string;
  description?: string;
  org_id?: string;
}

export interface TestSession {
  id: string;
  project_id?: string | null;
  session_name: string;
  mode: SessionMode;
  status: SessionStatus;
  duration_ms: number;
  total_interactions: number;
  total_tokens: number;
  total_cost_usd: number;
  fixture_storage_path?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface TestSessionCreate {
  session_name: string;
  project_id?: string;
  mode?: SessionMode;
  status?: SessionStatus;
  duration_ms?: number;
  total_interactions?: number;
  total_tokens?: number;
  total_cost_usd?: number;
  fixture_storage_path?: string;
  metadata?: Record<string, unknown>;
}


export interface ToolExecution {
   id?: string;
  interaction_id?: string;
  tool_name: string;
  tool_call_id?: string | null;
  arguments: Record<string, unknown>;
  output?: Record<string, unknown> | string | null;
  duration_ms: number;
  status: "success" | "error";
  error_message?: string | null;
}


export interface Interaction {
  id: string;
  session_id: string;
  step_index: number;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  semantic_similarity?: number | null;
  token_diff?: Record<string, unknown> | null;
  is_cache_hit: boolean;
  created_at: string;
  tools?: ToolExecution[];
}


export interface ModelUsageStat {
  model: string;
  provider: string;
  count: number;
  total_tokens: number;
  total_cost_usd: number;
}

export interface LatencyDistribution {
  p50_ms: number;
  p90_ms: number;
  p99_ms: number;
}


export interface AnalyticsOverview {
  total_sessions: number;
  total_interactions: number;
  total_replays: number;
  estimated_cost_saved_usd: number;
  total_tokens_recorded: number;
  replay_success_rate: number;
  average_latency_ms: number;
  top_models: ModelUsageStat[];
  latency_distribution?: LatencyDistribution | null;
}


export interface SessionFilterParams {
  project_id?: string;
  session?: SessionStatus;
  mode?: string;
  search?: string;
  limit?: number;
  offset?: number;
}
