import { apiClient } from './client';

export interface TradingHistoryRefreshResponse {
  updated: number;
  failed: number;
  total: number;
  errors: Array<{ secid: string; error: string }>;
}

/**
 * Запускает обновление истории торгов по всем облигациям.
 * Бэкенд сам получает список из bonds.json; фронтенд не передаёт данных.
 */
export const refreshTradingHistory = async (): Promise<TradingHistoryRefreshResponse> => {
  const response = await apiClient.get<TradingHistoryRefreshResponse>(
    '/trading-history/download',
    { timeout: 600_000 }
  );
  return response.data;
};
