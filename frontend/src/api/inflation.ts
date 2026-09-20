import axios from 'axios';

export interface InflationDataLoadResponse {
  status: string;
  data?: unknown;
}

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
 * Загрузка Excel-файла данных по инфляции на сервер и запуск его парсинга.
 */
export const uploadAndParseInflationFile = async (file: File): Promise<InflationDataLoadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await conversionClient.post<InflationDataLoadResponse>(
      '/inflations/upload_inflation_data',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return response.data;
  } catch {
    // Резервный вызов напрямую к conversion_service на порт 12345
    const fallbackResponse = await axios.post<InflationDataLoadResponse>(
      'http://127.0.0.1:12345/api/inflations/upload_inflation_data',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      }
    );
    return fallbackResponse.data;
  }
};