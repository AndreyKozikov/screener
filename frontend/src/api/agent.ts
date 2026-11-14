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

export interface AgentChatSummary { session_id: string; title: string; updated_at: string; preview?: string | null }
export interface AgentStoredChat extends AgentChatSummary { messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string; intent?: string | null; sources?: AgentSource[] }> }

/**
 * Отправляет сообщение ИИ-агенту подбора облигаций.
 */
export const sendAgentQuery = async (
  payload: AgentChatRequest
): Promise<AgentChatResponse> => {
  const response = await apiClient.post<AgentChatResponse>('/agent/chat', payload);
  return response.data;
};

export const listAgentChats = async (): Promise<AgentChatSummary[]> => (await apiClient.get<AgentChatSummary[]>('/agent/chats')).data;
export const fetchAgentChat = async (id: string): Promise<AgentStoredChat> => (await apiClient.get<AgentStoredChat>(`/agent/chats/${encodeURIComponent(id)}`)).data;
export const deleteAgentChat = async (id: string): Promise<void> => { await apiClient.delete(`/agent/chats/${encodeURIComponent(id)}`); };
