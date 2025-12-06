import { apiClient } from './client';

export interface EmitentInfo {
  is_traded?: number | null;
  emitent_title?: string | null;
  emitent_inn?: string | null;
  type?: string | null;
}

/**
 * Get emitent information by SECID
 */
export const getEmitentBySecid = async (secid: string): Promise<EmitentInfo> => {
  const response = await apiClient.get<EmitentInfo>(`/emitent/${secid}`);
  return response.data;
};

/**
 * Refresh emitents data for all bonds
 * Backend will read bonds.json and update emitent data for each bond
 */
export const refreshEmitentsData = async (): Promise<void> => {
  await apiClient.post('/emitent/refresh');
};

