import axios from 'axios';

// Определяем базовый URL для API
// Если VITE_API_BASE_URL установлен, используем его
// Иначе используем относительный путь - Vite будет проксировать запросы на бэкенд
const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  
  // Если переменная окружения установлена и не пустая
  if (envUrl && envUrl.trim() !== '') {
    return envUrl;
  }
  
  // Используем относительный путь - Vite proxy или nginx будет проксировать запросы
  // Это работает как для режима разработки (Vite proxy), так и для production (nginx)
  return '/api';
};

const API_BASE_URL = getApiBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    const baseURL = config.baseURL || '';
    const url = config.url || '';
    console.log('[API Client] Request:', config.method?.toUpperCase(), baseURL + url);
    if (config.params) {
      console.log('[API Client] Request params:', config.params);
    }
    return config;
  },
  (error) => {
    console.error('[API Client] Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    console.log('[API Client] Response:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('[API Client] Response error:', error);
    if (error.response) {
      // Server responded with error
      console.error('[API Client] Error response:', error.response.status, error.response.data);
      const message = error.response.data?.detail || 'Server error';
      return Promise.reject(new Error(message));
    } else if (error.request) {
      // Request made but no response
      console.error('[API Client] No response from server. Request:', error.request);
      console.error('[API Client] Request URL:', error.config?.url);
      console.error('[API Client] Base URL:', error.config?.baseURL);
      return Promise.reject(new Error('Network error - no response from server'));
    } else {
      // Request setup error
      console.error('[API Client] Request setup error:', error.message);
      return Promise.reject(error);
    }
  }
);
