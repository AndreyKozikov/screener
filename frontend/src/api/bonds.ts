import { apiClient } from './client';
import type { BondsListResponse } from '../types/api';
import type { BondDetail } from '../types/bond';
import type { BondFilters } from '../types/filters';
import type { CouponsListResponse } from '../types/coupon';

/**
 * Fetch filtered bonds list
 * Loads ALL filtered data in one request for client-side pagination and search
 * Search filtering is done on client side, not sent to server
 */
export const fetchBonds = async (filters: BondFilters): Promise<BondsListResponse> => {
  const params: Record<string, string | number | (string | number)[] | null> = {};
  
  // Build query parameters (exclude search and skip/limit for client-side operations)
  if (filters.couponMin !== null) params.coupon_min = filters.couponMin;
  if (filters.couponMax !== null) params.coupon_max = filters.couponMax;
  if (filters.matdateFrom) params.matdate_from = filters.matdateFrom;
  if (filters.matdateTo) params.matdate_to = filters.matdateTo;
  if (filters.listlevel.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: listlevel=1&listlevel=2
    // Convert numbers to strings for URL serialization
    params.listlevel = filters.listlevel.map(String);
  }
  if (filters.faceunit.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: faceunit=RUB&faceunit=USD
    params.faceunit = filters.faceunit;
  }
  // Note: search is NOT sent to server - it will be filtered on client side
  // Note: skip/limit are NOT sent - we load all data by not sending limit parameter
  
  // Load all filtered data in one request (limit is not sent, so backend returns all)
  // Use paramsSerializer to ensure arrays are serialized correctly for FastAPI
  const response = await apiClient.get<BondsListResponse>('/api/bonds', { 
    params,
    paramsSerializer: (params) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value === null || value === undefined) {
          return;
        }
        if (Array.isArray(value)) {
          // For arrays, add each value as a separate query parameter
          value.forEach((item) => {
            searchParams.append(key, String(item));
          });
        } else {
          searchParams.append(key, String(value));
        }
      });
      return searchParams.toString();
    },
  });
  
  // Apply client-side search filter if provided
  let allBonds = response.data.bonds;
  let filteredCount = response.data.filtered;
  
  if (filters.search && filters.search.trim()) {
    const searchLower = filters.search.toLowerCase().trim();
    allBonds = allBonds.filter(bond => {
      const secid = (bond.SECID || '').toLowerCase();
      const shortname = (bond.SHORTNAME || '').toLowerCase();
      return secid.includes(searchLower) || shortname.includes(searchLower);
    });
    filteredCount = allBonds.length;
  }
  
  return {
    total: response.data.total,
    filtered: filteredCount,
    skip: 0,
    limit: allBonds.length,
    bonds: allBonds,
  };
};

/**
 * Fetch bond details by SECID
 */
export const fetchBondDetail = async (secid: string): Promise<BondDetail> => {
  const response = await apiClient.get<BondDetail>(`/api/bonds/${secid}`);
  return response.data;
};

/**
 * Export bonds to JSON
 */
export const exportBondsJson = (bonds: Array<Record<string, unknown>>): void => {
  const dataStr = JSON.stringify(bonds, null, 2);
  const dataBlob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(dataBlob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = `bonds_export_${new Date().toISOString().split('T')[0]}.json`;
  link.click();
  
  URL.revokeObjectURL(url);
};

/**
 * Request a dataset refresh from the backend
 */
export const refreshBondsData = async (): Promise<void> => {
  await apiClient.post('/api/bonds/refresh');
};

/**
 * Fetch bond coupons by SECID
 */
export const fetchBondCoupons = async (secid: string, forceRefresh: boolean = false): Promise<CouponsListResponse> => {
  const params: Record<string, boolean> = {};
  if (forceRefresh) {
    params.force_refresh = true;
  }
  const response = await apiClient.get<CouponsListResponse>(`/api/bonds/${secid}/coupons`, { params });
  return response.data;
};
