import { apiClient } from './client';

export interface KeyRateData {
  [date: string]: number; // date in YYYY-MM-DD format, value is rate (float)
}

export interface KeyRateRecord {
  'Дата': string;
  'Ключевая ставка, % годовых': number;
}

export interface KeyRateDataResponse {
  data: KeyRateRecord[];
  count: number;
  date_from: string | null;
  date_to: string | null;
}

/**
 * Load key rate data from CBR HTML page and save to JSON file
 * 
 * @returns Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
 */
export const loadKeyRateData = async (): Promise<KeyRateData> => {
  const response = await apiClient.post<KeyRateData>('/keyrate/load');
  return response.data;
};

/**
 * Get key rate data from local JSON file
 * 
 * @returns Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
 */
export const getKeyRateData = async (): Promise<KeyRateData> => {
  const response = await apiClient.get<KeyRateData>('/keyrate/data');
  return response.data;
};

/**
 * Fetch key rate data filtered by date range
 */
export const fetchKeyRateData = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<KeyRateDataResponse> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get<KeyRateDataResponse>('/keyrate/data', { params });
  return response.data;
};

/**
 * Download key rate data as Markdown
 */
export const downloadKeyRateMarkdown = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<void> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get('/keyrate/download/markdown', {
    params,
    responseType: 'blob',
  });

  // Create download link
  const blob = new Blob([response.data], { type: 'text/markdown;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Generate filename
  let filename = 'keyrate';
  if (dateFrom || dateTo) {
    if (dateFrom) filename += `_${dateFrom.replace(/\./g, '-')}`;
    if (dateTo) filename += `_${dateTo.replace(/\./g, '-')}`;
  } else {
    filename += '_all';
  }
  filename += '.md';

  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};
