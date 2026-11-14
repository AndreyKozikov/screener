import { apiClient } from './client';

export const refreshFloatersData = async (provider: string = 'gemini'): Promise<void> => {
  await apiClient.post('/float-bonds-llm-analize/run', {
    provider,
    use_local_events: true,
  }, { timeout: 1_200_000 });
};



