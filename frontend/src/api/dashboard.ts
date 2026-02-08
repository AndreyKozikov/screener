import { apiClient } from './client';

/** Один курс валюты в ответе плашки (совпадает с бэкенд CurrencyRateItem). */
export interface DashboardCurrencyRateItem {
  code: string;
  rate: number;
  nominal?: number;
  original_value?: string;
}

/** Ответ эндпоинта GET /api/dashboard/rates — данные для плашки без преобразований. */
export interface MacroRatesResponse {
  date: string;
  source_date: string;
  rates: Record<string, DashboardCurrencyRateItem>;
  ruonia_rate: number | null;
  key_rate: number | null;
}

/**
 * Загружает данные для плашки главной страницы: курсы валют, RUONIA, ключевая ставка.
 * Один запрос к бэкенду; данные отображаются как есть.
 */
export const getDashboardRates = async (): Promise<MacroRatesResponse> => {
  const response = await apiClient.get<MacroRatesResponse>('/dashboard/rates');
  return response.data;
};
