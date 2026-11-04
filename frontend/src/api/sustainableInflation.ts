import { apiClient } from './client';

export interface SustainableInflationDataPoint {
  record_date: string;
  trend_inflation_3y: number | null;
  trend_inflation_5y: number | null;
  modified_core_inflation: number | null;
}

export interface SustainableInflationDateRange {
  from?: string;
  till?: string;
}

export const fetchSustainableInflationData = async (
  dateRange: SustainableInflationDateRange = {},
): Promise<SustainableInflationDataPoint[]> => {
  const response = await apiClient.post<SustainableInflationDataPoint[]>(
    '/inflations/sustainable',
    dateRange,
  );
  return response.data;
};
