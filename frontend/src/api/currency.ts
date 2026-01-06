import { apiClient } from './client';

export interface CurrencyRate {
  code: string;
  rate: number;
  nominal: number;
  original_value: string;
}

export interface CurrencyRatesResponse {
  date: string;
  source_date: string;
  rates: {
    [key: string]: CurrencyRate;
  };
}

/**
 * Get currency exchange rates (EUR, USD, CNY) for the given date
 * 
 * @param targetDate - Date to get rates for (YYYY-MM-DD), defaults to today
 */
export const getCurrencyRates = async (targetDate?: string): Promise<CurrencyRatesResponse> => {
  const response = await apiClient.get<CurrencyRatesResponse>('/currency/rates', {
    params: targetDate ? { target_date: targetDate } : undefined
  });
  return response.data;
};

/**
 * Force refresh currency exchange rates from CBR API for the given date
 * 
 * @param targetDate - Date to refresh rates for (YYYY-MM-DD), defaults to today
 */
export const refreshCurrencyRates = async (targetDate?: string): Promise<{
  status: string;
  date: string;
  rates_count: number;
  updated: boolean;
  error?: string;
}> => {
  const response = await apiClient.post('/currency/refresh', null, {
    params: targetDate ? { target_date: targetDate } : undefined
  });
  return response.data;
};

