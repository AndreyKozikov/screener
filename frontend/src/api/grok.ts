import { apiClient } from './client';

export interface GrokAnalysisResponse {
  analysis: string;  // Финальный отчет (этап 5)
  model_used: string;
  stage1_forecast?: string | null;  // Этап 1: Прогноз Банка России
  stage2_zerocupon?: string | null;  // Этап 2: Кривая бескупонной доходности
  stage3_bonds?: string | null;  // Этап 3: Нормализация данных по облигациям
}

/**
 * Analyze bonds using Grok 4.1 Fast via OpenRouter with file uploads
 */
export const analyzeBondsWithGrok = async (
  bondsData: string,
  zerocuponData: string,
  forecastData: string,
  model: string = 'x-ai/grok-4.1-fast:free',
  includeZerocupon: boolean = true,
  includeForecast: boolean = true
): Promise<GrokAnalysisResponse> => {
  // Create Blob objects from JSON strings
  const bondsBlob = new Blob([bondsData], { type: 'application/json' });
  const bondsFile = new File([bondsBlob], 'bonds_data.json', { type: 'application/json' });
  
  // Create FormData - bonds file is always included
  const formData = new FormData();
  formData.append('bonds_file', bondsFile);
  
  // Add zerocupon file only if included
  if (includeZerocupon && zerocuponData) {
    const zerocuponBlob = new Blob([zerocuponData], { type: 'application/json' });
    const zerocuponFile = new File([zerocuponBlob], 'zerocupon_data.json', { type: 'application/json' });
    formData.append('zerocupon_file', zerocuponFile);
  }
  
  // Add forecast file only if included
  if (includeForecast && forecastData) {
    const forecastBlob = new Blob([forecastData], { type: 'application/json' });
    const forecastFile = new File([forecastBlob], 'forecast_data.json', { type: 'application/json' });
    formData.append('forecast_file', forecastFile);
  }
  
  formData.append('model', model);
  
  // Send multipart/form-data request with extended timeout (20 minutes for Grok analysis)
  const response = await apiClient.post<GrokAnalysisResponse>(
    '/grok/analyze',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 1200000, // 20 minutes (1200000 ms) - Grok analysis can take a long time
    }
  );
  
  return response.data;
};

