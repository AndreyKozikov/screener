export interface IpcMonthlyPoint {
  record_data: string;
  ipc: number | null;
  food_ipc: number | null;
  non_food_ipc: number | null;
  services_ipc: number | null;
}

export interface IpcWeeklyPoint {
  start_date: string;
  end_date: string;
  ipc_weekly: number | null;
}

export interface IpcDashboardData {
  monthly: IpcMonthlyPoint[];
  weekly: IpcWeeklyPoint[];
  kpi: {
    monthly: { index: number | null; inflation: number | null; change: number | null; date: string | null };
    weekly: {
      index: number | null;
      inflation: number | null;
      change: number | null;
      start_date: string | null;
      end_date: string | null;
    };
    year_to_date: {
      inflation: number | null;
      year: number;
      from_date: string | null;
      to_date: string | null;
    };
    twelve_month: {
      index: number | null;
      inflation: number | null;
      change: number | null;
      from_date: string | null;
      to_date: string | null;
    };
    last_observation_date: string | null;
  };
}
