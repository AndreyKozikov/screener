import { conversionApiClient } from './client';

export interface TradingHistoryRefreshResponse {
  updated: number;
  failed: number;
  total: number;
  errors: Array<{ secid: string; error: string }>;
}

/**
 * Запускает обновление истории торгов по всем облигациям через conversion_service.
 * Список облигаций загружается сервисом; фронтенд его не передаёт.
 */
export const refreshTradingHistory = async (): Promise<TradingHistoryRefreshResponse> => {
  const response = await conversionApiClient.get<TradingHistoryRefreshResponse>(
    '/trading-history/download',
    { timeout: 600_000 }
  );
  return response.data;
};



