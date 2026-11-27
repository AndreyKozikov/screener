import { apiClient } from './client';

export type DataUpdateStatusValue = 'running' | 'success' | 'error';
export type DataUpdateTrigger = 'manual' | 'scheduled';

export interface DataUpdateStatusItem {
  task_id: string;
  status: DataUpdateStatusValue | null;
  trigger: DataUpdateTrigger | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  warning_message: string | null;
  run_id: string | null;
  log_available: boolean;
}

export interface DataUpdateStatusesResponse {
  generated_at: string;
  items: DataUpdateStatusItem[];
}

export interface DataUpdateRunDetail extends DataUpdateStatusItem {
  log: string | null;
}

export const fetchDataUpdateStatuses = async (): Promise<DataUpdateStatusesResponse> => {
  const { data } = await apiClient.get<DataUpdateStatusesResponse>('/admin/data-updates');
  return data;
};

export const fetchDataUpdateRun = async (runId: string): Promise<DataUpdateRunDetail> => {
  const { data } = await apiClient.get<DataUpdateRunDetail>(`/admin/data-updates/runs/${runId}`);
  return data;
};
