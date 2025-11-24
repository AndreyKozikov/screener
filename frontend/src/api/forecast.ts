import { apiClient } from './client';

export interface ForecastValue {
  мин: number;
  макс: number;
}

export interface ForecastIndicator {
  год: number;
  [key: string]: number | ForecastValue | null;
}

export interface ForecastBalance {
  год: number;
  [key: string]: number | null;
}

export interface ForecastData {
  date: string;
  names: {
    основные_показатели: Record<string, string>;
    платёжный_баланс: Record<string, string>;
  };
  data: {
    дата_заседания: string;
    дата_публикации: string;
    основные_показатели: ForecastIndicator[];
    платёжный_баланс: ForecastBalance[];
  };
}

export interface ForecastDatesResponse {
  dates: string[];
}

/**
 * Get list of available forecast dates
 */
export const fetchForecastDates = async (): Promise<string[]> => {
  const response = await apiClient.get<ForecastDatesResponse>('/api/forecast/dates');
  return response.data.dates;
};

/**
 * Fetch forecast data for a specific date (or latest if not provided)
 */
export const fetchForecastData = async (date?: string | null): Promise<ForecastData> => {
  const params: Record<string, string> = {};
  if (date) params.date = date;

  const response = await apiClient.get<ForecastData>('/api/forecast/data', { params });
  return response.data;
};

/**
 * Download forecast data as JSON file
 */
export const downloadForecastJson = async (dates?: string[] | null): Promise<void> => {
  const params: Record<string, string> = {};
  if (dates && dates.length > 0) {
    params.dates = dates.join(',');
  }

  const response = await apiClient.get('/api/forecast/export/json', {
    params,
    responseType: 'blob',
  });

  // Create download link
  const blob = new Blob([response.data], { type: 'application/json;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Generate filename from response headers or default
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'forecast.json';
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="(.+)"/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }

  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

