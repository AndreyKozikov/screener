import { apiClient } from './client';

export interface InflationExpectationsDataPoint {
  recorddata: string;
  observed_annual_inflation: number | null;
  expected_annual_inflation: number | null;
  expected_five_year_inflation: number | null;
  expectations_index: number | null;
}

/**
 * Fetch inflation expectations data with optional date range
 * @param params Date range parameters (from and till dates)
 * @returns Array of inflation expectations data points
 */
export const fetchInflationExpectationsData = async (params: { 
  from?: string; 
  till?: string 
} = {}): Promise<InflationExpectationsDataPoint[]> => {
  try {
    const requestData: { from?: string; till?: string } = {};
    if (params.from) {
      requestData.from = params.from;
    }
    if (params.till) {
      requestData.till = params.till;
    }
    
    const response = await apiClient.post<InflationExpectationsDataPoint[]>(
      '/inflations/get_data',
      requestData
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching inflation expectations data:', error);
    throw error;
  }
};