import { apiClient } from './client';

export type AgentLogEvent = Record<string, unknown> & {
  ts?: string;
  type?: string;
};

export interface AgentSessionSummary {
  session_id: string;
  first_query: string;
  created_at: string | null;
  updated_at: string | null;
  query_count: number;
  event_count: number;
  issue_count: number;
  with_portfolio: boolean;
  outcome: string | null;
  log_source: 'current' | 'legacy';
}

export interface AgentSessionListResponse {
  items: AgentSessionSummary[];
  total: number;
  offset: number;
  limit: number;
  logging_enabled: boolean;
}

export interface AgentSessionDetail extends AgentSessionSummary {
  metadata: Record<string, unknown>;
  events: AgentLogEvent[];
  parse_errors: number;
}

export const fetchAgentSessions = async (params: {
  q?: string;
  offset?: number;
  limit?: number;
  problem_only?: boolean;
} = {}): Promise<AgentSessionListResponse> => {
  const response = await apiClient.get<AgentSessionListResponse>('/admin/agent-sessions', { params });
  return response.data;
};

export const fetchAgentSession = async (sessionId: string): Promise<AgentSessionDetail> => {
  const response = await apiClient.get<AgentSessionDetail>(
    `/admin/agent-sessions/${encodeURIComponent(sessionId)}`,
  );
  return response.data;
};
