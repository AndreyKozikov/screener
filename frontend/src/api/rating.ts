import { apiClient } from './client';

export interface Rating {
  agency_id: number;
  agency_name_short_ru: string;
  rating_level_id: number;
  rating_date: string;
  rating_level_name_short_ru: string;
}

/**
 * Get bond rating by SECID and BOARDID
 */
export const getBondRating = async (secid: string, boardid: string): Promise<Rating[]> => {
  const response = await apiClient.get<Rating[]>(`/rating/${secid}`, {
    params: { boardid }
  });
  return response.data;
};

/**
 * Refresh ratings data for all bonds
 * Backend will read bonds.json and update ratings for each bond
 * 
 * @param forceUpdate - If true, force update all ratings regardless of last_updated date
 */
export const refreshRatingsData = async (forceUpdate: boolean = false): Promise<void> => {
  await apiClient.post('/rating/refresh', null, {
    params: { force_update: forceUpdate }
  });
};

