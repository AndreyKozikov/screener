import axios from 'axios';
import type { IpcData, IpcLoadResponse } from '../types/ipc';

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
 * Загрузка Excel-файла ИПЦ на сервер и запуск его парсинга.
 */
export const uploadAndParseIpcFile = async (file: File): Promise<IpcLoadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await conversionClient.post<IpcLoadResponse>('/ipc/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (err) {
    // Резервный вызов напрямую к conversion_service на порт 12345
    const fallbackResponse = await axios.post<IpcLoadResponse>(
      'http://127.0.0.1:12345/api/ipc/upload',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      }
    );
    return fallbackResponse.data;
  }
};

/**
 * Запуск парсинга локального файла ИПЦ на сервере.
 */
export const parseLocalIpcFile = async (filePath?: string): Promise<IpcLoadResponse> => {
  const params = filePath ? { file_path: filePath } : {};

  try {
    const response = await conversionClient.post<IpcLoadResponse>('/ipc/parse-local', null, { params });
    return response.data;
  } catch (err) {
    // Резервный вызов напрямую к conversion_service на порт 12345
    const fallbackResponse = await axios.post<IpcLoadResponse>(
      'http://127.0.0.1:12345/api/ipc/parse-local',
      null,
      { params, timeout: 120000 }
    );
    return fallbackResponse.data;
  }
};

/**
 * Получение сохранённых данных ИПЦ из JSON-файла.
 */
export const fetchSavedIpcData = async (): Promise<IpcData> => {
  try {
    const response = await conversionClient.get<IpcData>('/ipc/data');
    return response.data;
  } catch (err) {
    const fallbackResponse = await axios.get<IpcData>(
      'http://127.0.0.1:12345/api/ipc/data',
      { timeout: 30000 }
    );
    return fallbackResponse.data;
  }
};

/**
 * Запуск загрузки и парсинга еженедельного ИПЦ.
 */
export const uploadIpcWeekly = async (): Promise<unknown> => {
  try {
    const response = await conversionClient.post('/ipc/upload_ipc_weekly');
    return response.data;
  } catch (err) {
    // Резервный вызов напрямую к conversion_service на порт 12345
    const fallbackResponse = await axios.post(
      'http://127.0.0.1:12345/api/ipc/upload_ipc_weekly',
      null,
      { timeout: 120000 }
    );
    return fallbackResponse.data;
  }
};

