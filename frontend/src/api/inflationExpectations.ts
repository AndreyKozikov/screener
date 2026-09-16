import axios from 'axios';
import type { InflationExpectationsLoadResponse } from '../types/inflationExpectations';

const getConversionApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_CONVERSION_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '') {
    return envUrl;
  }
  return 'http://127.0.0.1:12345/api';
};

export const conversionClient = axios.create({
  baseURL: getConversionApiBaseUrl(),
  timeout: 120000,
});

/**
 * Загрузка Excel-файла инфляционных ожиданий на сервер и запуск его парсинга.
 */
export const uploadAndParseInflationExpectationsFile = async (file: File): Promise<InflationExpectationsLoadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await conversionClient.post<InflationExpectationsLoadResponse>(
      '/inflation-expectations/upload',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return response.data;
  } catch {
    // Резервный вызов напрямую к conversion_service на порт 12345
    const fallbackResponse = await axios.post<InflationExpectationsLoadResponse>(
      'http://127.0.0.1:12345/api/inflation-expectations/upload',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      }
    );
    return fallbackResponse.data;
  }
};