import { conversionApiClient } from './client';

export interface InflationDataLoadResponse {
  status: string;
  data?: unknown;
}

const conversionClient = conversionApiClient;

/**
 * Загрузка Excel-файла данных по инфляции на сервер и запуск его парсинга.
 */
export const uploadAndParseInflationFile = async (file: File): Promise<InflationDataLoadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await conversionClient.post<InflationDataLoadResponse>(
    '/inflations/upload_inflation_data',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
  );
  return response.data;
};

/**
 * Отправка URL на Excel-файл данных по инфляции: сервис сам скачивает файл,
 * обрабатывает его и удаляет скачанный файл после успешной обработки.
 */
export const uploadAndParseInflationByUrl = async (url: string): Promise<InflationDataLoadResponse> => {
  const response = await conversionClient.post<InflationDataLoadResponse>(
    '/inflations/upload_inflation_data_by_url',
    { url },
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );
  return response.data;
};


