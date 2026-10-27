import { apiClient } from './client';
import type { IpcDashboardData } from '../types/ipcData';

export const fetchIpcDashboardData = async (): Promise<IpcDashboardData> => {
  const response = await apiClient.get<IpcDashboardData>('/ipc/data');
  return response.data;
};



