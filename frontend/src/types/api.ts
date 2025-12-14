/**
 * API response structures
 */

import type { BondListItem } from './bond';

export interface BondsListResponse {
  total: number;
  filtered: number;
  skip: number;
  limit: number;
  bonds: BondListItem[];
}

export interface ColumnMapping {
  [fieldName: string]: string;  // e.g., {"SECID": "Код инструмента"}
}

export interface ApiError {
  detail: string;
  error_code?: string;
}
