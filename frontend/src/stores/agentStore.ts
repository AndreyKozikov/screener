import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { sendAgentQuery, listAgentChats, fetchAgentChat, deleteAgentChat, type AgentSource, type AgentChatSummary } from '../api/agent';
import { usePortfolioStore } from './portfolioStore';

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: AgentSource[];
  /** Применённые параметры поиска (только у ответов после search_bonds). */
  filters?: Record<string, unknown>;
  timestamp: number;
}

interface AgentState {
  sessionId: string | null;
  messages: AgentMessage[];
  isLoading: boolean;
  error: string | null;
  chats: AgentChatSummary[];
  loadChats: () => Promise<void>;
  openChat: (id: string) => Promise<void>;
  removeChat: (id: string) => Promise<void>;
  resetChat: () => void;
  send: (query: string) => Promise<void>;
  /** Начинает новый чистый диалог с запроса и сразу отправляет его. */
  sendNew: (query: string) => Promise<void>;
}

const newId = (): string =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      messages: [],
      isLoading: false,
      error: null,
      chats: [],

      loadChats: async () => { try { set({ chats: await listAgentChats() }); } catch { /* keep current view */ } },
      openChat: async (id) => {
        const chat = await fetchAgentChat(id);
        set({ sessionId: chat.session_id, messages: chat.messages.map((m, index) => ({
          id: `${chat.session_id}-${index}`, role: m.role, content: m.content,
          timestamp: Date.parse(m.timestamp) || Date.now(), sources: m.sources ?? [],
        })), error: null });
      },
      removeChat: async (id) => { await deleteAgentChat(id); set((s) => ({ chats: s.chats.filter((c) => c.session_id !== id), ...(s.sessionId === id ? { sessionId: null, messages: [] } : {}) })); },

      resetChat: () => set({ sessionId: null, messages: [], error: null }),

      sendNew: async (query) => {
        set({ sessionId: null, messages: [], error: null, isLoading: false });
        await get().send(query);
      },

      send: async (query) => {
        const trimmed = query.trim();
        if (!trimmed || get().isLoading) return;

        const sessionId = get().sessionId ?? newId();
        const userMsg: AgentMessage = {
          id: newId(),
          role: 'user',
          content: trimmed,
          timestamp: Date.now(),
        };

        set((s) => ({
          sessionId,
          isLoading: true,
          error: null,
          messages: [...s.messages, userMsg],
        }));

        try {
          const portfolioBonds = usePortfolioStore.getState().portfolioBonds;
          const response = await sendAgentQuery({
            query: trimmed,
            session_id: sessionId,
            portfolio: portfolioBonds,
            history: get().messages.slice(0, -1).map(({ role, content }) => ({ role, content })),
          });

          const content =
            response.state === 'done' && response.answer
              ? response.answer
              : response.state === 'error'
                ? (response.answer ?? 'Извините, произошла ошибка. Попробуйте ещё раз.')
                : (response.question ?? 'Не удалось получить ответ.');

          const botMsg: AgentMessage = {
            id: newId(),
            role: 'assistant',
            content,
            sources: response.sources ?? [],
            filters: response.filters ?? undefined,
            timestamp: Date.now(),
          };

          set((s) => ({ messages: [...s.messages, botMsg], isLoading: false }));
          void get().loadChats();
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Не удалось связаться с сервером.';
          set({ isLoading: false, error: message });
        }
      },
    }),
    {
      name: 'bonds-screener:agent',
      partialize: (s) => ({ sessionId: s.sessionId, messages: s.messages }),
    }
  )
);
