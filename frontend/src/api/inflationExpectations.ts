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

  const response = await conversionClient.post<InflationExpectationsLoadResponse>(
    '/inflations/upload',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return response.data;
};

/**
 * Отправка URL на Excel-файл инфляционных ожиданий: сервис сам скачивает файл,
 * обрабатывает его и удаляет скачанный файл после успешной обработки.
 */
export const uploadAndParseInflationExpectationsByUrl = async (url: string): Promise<InflationExpectationsLoadResponse> => {
  const response = await conversionClient.post<InflationExpectationsLoadResponse>(
    '/inflations/upload_by_url',
    { url },
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );
  return response.data;
};


