import { conversionApiClient } from './client';
import type { InflationExpectationsLoadResponse } from '../types/inflationExpectations';

const conversionClient = conversionApiClient;

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


