import { apiClient } from './client';

export interface RuoniaRefreshResponse {
  status: 'ok' | 'error';
  message?: string;
  from_date?: string;
  to_date?: string;
  new_entries?: number;
  updated_entries?: number;
  total_entries?: number;
  updated?: boolean;
  error?: string;
}

export interface RuoniaRecord {
  'Дата ставки': string;
  'Ставка RUONIA, % годовых': number | null;
  'Объем сделок RUONIA, млрд руб.': number | null;
  'Количество сделок, ед.': number | null;
  'Минимальная процентная ставка, % годовых': number | null;
  '25-й процентиль по процентным ставкам, % годовых': number | null;
  '75-й процентиль по процентным ставкам, % годовых': number | null;
  'Максимальная процентная ставка, % годовых': number | null;
}

export interface RuoniaDataResponse {
  data: RuoniaRecord[];
  count: number;
  date_from: string | null;
  date_to: string | null;
}

/**
 * Fetch RUONIA data filtered by date range
 */
export const fetchRuoniaData = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<RuoniaDataResponse> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get<RuoniaDataResponse>('/ruonia/data', { params });
  return response.data;
};

/**
 * Download RUONIA data as Markdown
 */
export const downloadRuoniaMarkdown = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<void> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get('/ruonia/download/markdown', {
    params,
    responseType: 'blob',
  });

  // Create download link
  const blob = new Blob([response.data], { type: 'text/markdown;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Generate filename
  let filename = 'ruonia';
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

/**
 * Request a refresh of RUONIA rate data from CBR
 */
export const refreshRuoniaData = async (): Promise<RuoniaRefreshResponse> => {
  const response = await apiClient.post<RuoniaRefreshResponse>('/ruonia/refresh');
  return response.data;
};
