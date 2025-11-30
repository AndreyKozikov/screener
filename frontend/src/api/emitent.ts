import { apiClient } from './client';

/**
 * Refresh emitents data for all bonds
 * Backend will read bonds.json and update emitent data for each bond
 */
export const refreshEmitentsData = async (): Promise<void> => {
  await apiClient.post('/emitent/refresh');
};

