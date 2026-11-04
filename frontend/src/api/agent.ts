import { apiClient } from './client';

export interface AgentSource {
  secid: string;
  shortname?: string;
}

export interface AgentTurnPayload {
  role: 'user' | 'assistant';
  content: string;
  intent?: 'ask' | 'tool' | 'answer' | null;
}

export interface AgentChatRequest {
  query: string;
  session_id?: string;
  history?: AgentTurnPayload[];
  portfolio?: unknown[];
}

export interface AgentChatResponse {
  session_id: string;
  state: 'needs_info' | 'done' | 'error';
  answer?: string | null;
  question?: string | null;
  sources: AgentSource[];
  /** Применённые параметры поиска облигаций (аргументы search_bonds). */
  filters?: Record<string, unknown> | null;
}

/**
 * Отправляет сообщение ИИ-агенту подбора облигаций.
 */
export const sendAgentQuery = async (
  payload: AgentChatRequest
): Promise<AgentChatResponse> => {
  const response = await apiClient.post<AgentChatResponse>('/agent/chat', payload);
  return response.data;
};