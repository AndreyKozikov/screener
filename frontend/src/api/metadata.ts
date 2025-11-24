import { apiClient } from './client';
import type { ColumnMapping } from '../types/api';
import type { FilterOptions } from '../types/filters';

/**
 * Fetch column name mappings
 */
export const fetchColumnMapping = async (): Promise<ColumnMapping> => {
  const response = await apiClient.get<ColumnMapping>('/api/columns');
  return response.data;
};

/**
 * Fetch field descriptions
 */
export interface DescriptionsResponse {
  [section: string]: Record<string, string>;
}

export const fetchDescriptions = async (): Promise<DescriptionsResponse> => {
  const response = await apiClient.get<DescriptionsResponse>('/api/descriptions');
  return response.data;
};

/**
 * Fetch available filter options
 */
export const fetchFilterOptions = async (): Promise<FilterOptions> => {
  const response = await apiClient.get<FilterOptions>('/api/filter-options');
  return response.data;
};
