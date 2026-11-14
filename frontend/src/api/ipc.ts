import { apiClient, conversionApiClient } from './client';
import type { IpcData, IpcLoadResponse } from '../types/ipc';

const conversionClient = conversionApiClient;

/**
 * Загрузка Excel-файла ИПЦ на сервер и запуск его парсинга.
 */
export const uploadAndParseIpcFile = async (file: File): Promise<IpcLoadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await conversionClient.post<IpcLoadResponse>('/ipc/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

/**
 * Запуск парсинга локального файла ИПЦ на сервере.
 */
export const parseLocalIpcFile = async (filePath?: string): Promise<IpcLoadResponse> => {
  const params = filePath ? { file_path: filePath } : {};

  const response = await conversionClient.post<IpcLoadResponse>('/ipc/parse-local', null, { params });
  return response.data;
};

/**
 * Получение сохранённых данных ИПЦ из JSON-файла.
 */
export const fetchSavedIpcData = async (): Promise<IpcData> => {
  const response = await apiClient.get<IpcData>('/ipc/data');
  return response.data;
};

/**
 * Запуск загрузки и парсинга еженедельного ИПЦ.
 */
export const uploadIpcWeekly = async (): Promise<unknown> => {
  const response = await conversionClient.post('/ipc/upload_ipc_weekly');
  return response.data;
};




