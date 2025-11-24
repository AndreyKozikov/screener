import { apiClient } from './client';

export interface ZerocuponRecord {
  Дата: string;
  Время: string;
  [key: string]: string | number | null; // Dynamic period columns
}

export interface ZerocuponDataResponse {
  data: ZerocuponRecord[];
  count: number;
  date_from: string | null;
  date_to: string | null;
}

/**
 * Fetch zero-coupon yield curve data filtered by date range
 */
export const fetchZerocuponData = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<ZerocuponDataResponse> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get<ZerocuponDataResponse>('/api/zerocupon/data', { params });
  return response.data;
};

/**
 * Download zero-coupon yield curve data as JSON
 */
export const downloadZerocuponJson = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<void> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const response = await apiClient.get('/api/zerocupon/download', {
    params,
    responseType: 'blob',
  });

  // Create download link
  const blob = new Blob([response.data], { type: 'application/json;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Generate filename
  let filename = 'zerocupon';
  if (dateFrom || dateTo) {
    if (dateFrom) filename += `_${dateFrom.replace(/\./g, '-')}`;
    if (dateTo) filename += `_${dateTo.replace(/\./g, '-')}`;
  } else {
    filename += '_last_year';
  }
  filename += '.json';

  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

