import { apiClient } from './client';

export interface KeyRateData {
  [date: string]: number; // date in YYYY-MM-DD format, value is rate (float)
}

export interface KeyRateRecord {
  'Дата': string;
  'Ключевая ставка, % годовых': number;
}

/**
 * Load key rate data from CBR and save to DB
 * @returns Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
 */
export const loadKeyRateData = async (): Promise<KeyRateData> => {
  const response = await apiClient.post<KeyRateData>('/keyrate/load');
  return response.data;
};

/**
 * Get key rate data as dict (all records). Backend returns array; we convert to dict.
 * @returns Dictionary with date (YYYY-MM-DD) as key and rate (float) as value
 */
export const getKeyRateData = async (): Promise<KeyRateData> => {
  const response = await apiClient.get<KeyRateRecord[]>('/keyrate/data');
  const arr = response.data;
  return Object.fromEntries(
    arr.map((d) => [d['Дата'], d['Ключевая ставка, % годовых']])
  ) as KeyRateData;
};

/**
 * Fetch key rate data filtered by date range (from/till in ISO YYYY-MM-DD).
 * Backend returns array of KeyRateRecord.
 */
export const fetchKeyRateData = async (
  fromISO?: string | null,
  tillISO?: string | null
): Promise<KeyRateRecord[]> => {
  const params: Record<string, string> = {};
  if (fromISO) params.from = fromISO;
  if (tillISO) params.till = tillISO;
  const response = await apiClient.get<KeyRateRecord[]>('/keyrate/data', { params });
  return response.data;
};

/**
 * Download key rate data as Markdown (from/till in ISO YYYY-MM-DD).
 */
export const downloadKeyRateMarkdown = async (
  fromISO?: string | null,
  tillISO?: string | null
): Promise<void> => {
  const params: Record<string, string> = {};
  if (fromISO) params.from = fromISO;
  if (tillISO) params.till = tillISO;
  const response = await apiClient.get('/keyrate/download/markdown', {
    params,
    responseType: 'blob',
  });
  const blob = new Blob([response.data], { type: 'text/markdown;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  let filename = 'keyrate';
  if (fromISO || tillISO) {
    if (fromISO) filename += `_${fromISO}`;
    if (tillISO) filename += `_${tillISO}`;
  } else {
    filename += '_all';
  }
  filename += '.md';
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};
