import { apiClient } from './client';

export const refreshFloatersData = async (provider: string = 'gemini'): Promise<void> => {
  await apiClient.post(`/edisclosure/update-floaters?provider=${provider}`);
};
