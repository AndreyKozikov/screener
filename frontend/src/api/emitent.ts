import { apiClient } from './client';

import type { Rating } from '../utils/ratings';

export interface EmitentInfo {
  is_traded?: number | null;
  emitent_title?: string | null;
  emitent_inn?: string | null;
  type?: string | null;
  cci_rating_companies?: Rating[] | null;
}

const emitentInfoRequests = new Map<string, Promise<EmitentInfo>>();

/** Clear cached issuer lookups after an explicit data refresh. */
export const clearEmitentInfoCache = (secid?: string): void => {
  if (secid) {
    emitentInfoRequests.delete(secid.trim().toUpperCase());
    return;
  }
  emitentInfoRequests.clear();
};

/**
 * Get emitent information by SECID, deduplicating and caching requests across
 * table row unmounts/remounts caused by virtualization.
 */
export const getEmitentBySecid = (secid: string): Promise<EmitentInfo> => {
  const cacheKey = secid.trim().toUpperCase();
  const cachedRequest = emitentInfoRequests.get(cacheKey);
  if (cachedRequest) return cachedRequest;

  const request = apiClient
    .get<EmitentInfo>(`/emitent/${encodeURIComponent(cacheKey)}`)
    .then((response) => response.data);
  emitentInfoRequests.set(cacheKey, request);
  return request;
};

/**
 * Refresh emitents data for all bonds
 * Backend will read bonds.json and update emitent data for each bond
 */
export const refreshEmitentsData = async (): Promise<void> => {
  await apiClient.post('/emitent/refresh');
  clearEmitentInfoCache();
};

/**
 * Get list of all unique emitent titles
 */
export interface EmitentListResponse {
  emitents: string[];
}

export const getEmitentList = async (): Promise<EmitentListResponse> => {
  const response = await apiClient.get<EmitentListResponse>('/emitent/list');
  return response.data;
};




