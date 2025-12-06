import { apiClient } from './client';
import type { ColumnMapping } from '../types/api';
import type { FilterOptions } from '../types/filters';

/**
 * Fetch column name mappings
 */
export const fetchColumnMapping = async (): Promise<ColumnMapping> => {
  const response = await apiClient.get<ColumnMapping>('/columns');
  if (!response.data) {
    throw new Error('Invalid response from server: missing column mapping data');
  }
  return response.data;
};

/**
 * Fetch field descriptions
 */
export interface DescriptionsResponse {
  [section: string]: Record<string, string>;
}

export const fetchDescriptions = async (): Promise<DescriptionsResponse> => {
  const response = await apiClient.get<DescriptionsResponse>('/descriptions');
  if (!response.data) {
    throw new Error('Invalid response from server: missing descriptions data');
  }
  return response.data;
};

/**
 * Fetch available filter options
 */
export const fetchFilterOptions = async (): Promise<FilterOptions> => {
  const response = await apiClient.get<FilterOptions>('/filter-options');
  if (!response.data) {
    throw new Error('Invalid response from server: missing filter options data');
  }
  // Убеждаемся, что массивы инициализированы
  return {
    listlevels: response.data.listlevels || [],
    faceunits: response.data.faceunits || [],
    bondtypes: response.data.bondtypes || [],
  };
};
