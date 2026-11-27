import { apiClient } from './client';

export type UpdateScheduleState =
  | 'scheduled'
  | 'paused'
  | 'disabled'
  | 'not_installed'
  | 'unknown';

export interface UpdateScheduleItem {
  task_id: string;
  timer_unit: string;
  service_unit: string;
  schedule: string | null;
  schedule_human: string | null;
  enabled: boolean | null;
  active: boolean | null;
  next_elapse: string | null;
  last_trigger_at: string | null;
  state: UpdateScheduleState;
  source: 'systemd' | 'files';
}

export interface UpdateScheduleResponse {
  generated_at: string;
  systemd_available: boolean;
  items: UpdateScheduleItem[];
}

export const fetchUpdateSchedule = async (): Promise<UpdateScheduleResponse> => {
  const { data } = await apiClient.get<UpdateScheduleResponse>('/admin/update-schedule');
  return data;
};
