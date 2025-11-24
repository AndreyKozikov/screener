import { apiClient } from './client';

export interface LLMAnalysisResponse {
  analysis: string;
  model_used: string;
}

/**
 * Analyze bonds using LLM with file uploads
 */
export const analyzeBondsWithLLM = async (
  bondsData: string,
  zerocuponData: string,
  forecastData: string,
  model: string = 'gpt-5-mini'
): Promise<LLMAnalysisResponse> => {
  // Create Blob objects from JSON strings
  const bondsBlob = new Blob([bondsData], { type: 'application/json' });
  const zerocuponBlob = new Blob([zerocuponData], { type: 'application/json' });
  const forecastBlob = new Blob([forecastData], { type: 'application/json' });
  
  // Create File objects with exact names as specified in prompt
  const bondsFile = new File([bondsBlob], 'bonds_data.json', { type: 'application/json' });
  const zerocuponFile = new File([zerocuponBlob], 'zerocupon_data.json', { type: 'application/json' });
  const forecastFile = new File([forecastBlob], 'forecast_data.json', { type: 'application/json' });
  
  // Create FormData
  const formData = new FormData();
  formData.append('bonds_file', bondsFile);
  formData.append('zerocupon_file', zerocuponFile);
  formData.append('forecast_file', forecastFile);
  formData.append('model', model);
  
  // Send multipart/form-data request with extended timeout (20 minutes for LLM analysis)
  const response = await apiClient.post<LLMAnalysisResponse>(
    '/api/llm/analyze',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 1200000, // 20 minutes (1200000 ms) - LLM analysis can take a long time
    }
  );
  
  return response.data;
};

