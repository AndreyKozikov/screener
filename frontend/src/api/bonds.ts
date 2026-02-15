import { apiClient } from './client';
import type { BondsListResponse } from '../types/api';
import type { BondDetail } from '../types/bond';
import type { BondFilters } from '../types/filters';
import type { CouponsListResponse, MultipleCouponsResponse } from '../types/coupon';

/**
 * Fetch filtered bonds list
 * Loads ALL filtered data in one request for client-side pagination and search
 * Search filtering is done on client side, not sent to server
 * @param excludeSpob If true, exclude bonds with trading mode SPOB
 */
export const fetchBonds = async (filters: BondFilters, emitentTitle?: string, excludeSpob?: boolean): Promise<BondsListResponse> => {
  const params: Record<string, string | number | (string | number)[] | boolean | null> = {};
  
  // Build query parameters (exclude search and skip/limit for client-side operations)
  if (filters.couponMin !== null) params.coupon_min = filters.couponMin;
  if (filters.couponMax !== null) params.coupon_max = filters.couponMax;
  if (filters.yieldMin !== null) params.yield_min = filters.yieldMin;
  if (filters.yieldMax !== null) params.yield_max = filters.yieldMax;
  if (filters.couponYieldMin !== null) params.coupon_yield_min = filters.couponYieldMin;
  if (filters.couponYieldMax !== null) params.coupon_yield_max = filters.couponYieldMax;
  if (filters.matdateFrom) params.matdate_from = filters.matdateFrom;
  if (filters.matdateTo) params.matdate_to = filters.matdateTo;
  if (emitentTitle) params.emitent_title = emitentTitle;
  if (excludeSpob === true) params.exclude_spob = true;
  if (filters.listlevel && Array.isArray(filters.listlevel) && filters.listlevel.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: listlevel=1&listlevel=2
    // Convert numbers to strings for URL serialization
    params.listlevel = filters.listlevel.map(String);
  }
  if (filters.faceunit && Array.isArray(filters.faceunit) && filters.faceunit.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: faceunit=RUB&faceunit=USD
    params.faceunit = filters.faceunit;
  }
  // bondtype и bondtype43 теперь содержат ID (числа) вместо строковых названий
  if (filters.bondtype && Array.isArray(filters.bondtype) && filters.bondtype.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: bondtype=1&bondtype=3
    params.bondtype = filters.bondtype.map(String);
  }
  if (filters.bondtype43 && Array.isArray(filters.bondtype43) && filters.bondtype43.length > 0) {
    // FastAPI expects array parameters to be sent as repeated query params: bondtype43=6&bondtype43=8
    params.bondtype43 = filters.bondtype43.map(String);
  }
  if (filters.ratingMin !== null) params.rating_min = filters.ratingMin;
  if (filters.ratingMax !== null) params.rating_max = filters.ratingMax;
  // Note: search is NOT sent to server - it will be filtered on client side
  // Note: skip/limit are NOT sent - we load all data by not sending limit parameter
  
  // Load all filtered data in one request (limit is not sent, so backend returns all)
  // Use paramsSerializer to ensure arrays are serialized correctly for FastAPI
  console.log('[Bonds API] Fetching bonds with filters:', filters);
  console.log('[Bonds API] Request params:', params);
  
  let response;
  try {
    // Сериализуем параметры вручную для правильной работы с FastAPI
    const paramsSerializer = (params: Record<string, any>): string => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value === null || value === undefined) {
          return;
        }
        if (Array.isArray(value)) {
          // For arrays, add each value as a separate query parameter (FastAPI format)
          value.forEach((item) => {
            searchParams.append(key, String(item));
          });
        } else {
          searchParams.append(key, String(value));
        }
      });
      const serialized = searchParams.toString();
      console.log('[Bonds API] Serialized params:', serialized);
      return serialized;
    };
    
    // Важно: эндпоинт определен как "/" с префиксом "/api/bonds", 
    // что означает полный путь "/api/bonds/" (с trailing slash)
    // FastAPI автоматически редиректит "/api/bonds" на "/api/bonds/", что вызывает 307
    // Используем "/bonds/" с trailing slash чтобы избежать редиректа
    const endpoint = '/bonds/';
    console.log('[Bonds API] Making request to:', apiClient.defaults.baseURL + endpoint);
    console.log('[Bonds API] Full URL will be:', apiClient.defaults.baseURL + endpoint + '?' + paramsSerializer(params));
    
    response = await apiClient.get<BondsListResponse>(endpoint, { 
      params,
      paramsSerializer,
    });
    
    console.log('[Bonds API] Response received:', response.status, response.data ? 'data OK' : 'no data');
  } catch (error) {
    console.error('[Bonds API] Error fetching bonds:', error);
    if (error instanceof Error) {
      console.error('[Bonds API] Error message:', error.message);
      if (error.stack) {
        console.error('[Bonds API] Error stack:', error.stack);
      }
    }
    throw error;
  }
  
  // Apply client-side search filter if provided
  // Проверяем, что данные есть
  if (!response || !response.data || !response.data.bonds) {
    console.error('[Bonds API] Invalid response:', response);
    throw new Error('Invalid response from server: missing bonds data');
  }
  
  let allBonds = response.data.bonds || [];
  let filteredCount = response.data.filtered || 0;
  
  if (filters.search && filters.search.trim()) {
    const searchLower = filters.search.toLowerCase().trim();
    allBonds = allBonds.filter(bond => {
      const secid = (bond.SECID || '').toLowerCase();
      const shortname = (bond.SHORTNAME || '').toLowerCase();
      const secname = (bond.SECNAME || '').toLowerCase();
      const isin = (bond.ISIN || '').toLowerCase();
      return secid.includes(searchLower) || 
             shortname.includes(searchLower) || 
             secname.includes(searchLower) || 
             isin.includes(searchLower);
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
 * Точка графика сравнения доходности облигации и RUONIA
 */
export interface YieldRuoniaChartPoint {
  date: string;
  ruonia_rate: number | null;
  yieldatwap: number | null;
}

/**
 * Ответ API графика доходность облигации vs RUONIA
 */
export interface YieldRuoniaChartResponse {
  secid: string;
  data: YieldRuoniaChartPoint[];
}

/**
 * Загружает данные для графика сравнения доходности облигации и ставки RUONIA.
 * Период: от (текущая дата − 1 день) на год назад; только даты, присутствующие в обоих источниках.
 */
export const fetchYieldRuoniaChart = async (secid: string): Promise<YieldRuoniaChartResponse> => {
  const response = await apiClient.get<YieldRuoniaChartResponse>(`/bonds/${secid}/yield-ruonia-chart`);
  return response.data;
};

/**
 * Fetch bond details by SECID
 */
export const fetchBondDetail = async (secid: string): Promise<BondDetail> => {
  const response = await apiClient.get<BondDetail>(`/bonds/${secid}`);
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
  await apiClient.post('/bonds/refresh');
};

/**
 * Request coupons data refresh for all bonds from the backend
 * @param forceRefresh If true, force refresh all coupons regardless of cache (ignore last_updated date)
 */
export const refreshCouponsData = async (forceRefresh: boolean = false): Promise<void> => {
  const params: Record<string, boolean> = {};
  if (forceRefresh) {
    params.force_refresh = true;
  }
  await apiClient.post('/bonds/refresh-coupons', null, { params });
};

/**
 * Fetch bond coupons by SECID (single bond)
 * @param secid Security ID
 * @param forceRefresh If true, force refresh from MOEX API
 */
export const fetchBondCoupons = async (secid: string, forceRefresh: boolean = false): Promise<CouponsListResponse> => {
  const params: Record<string, boolean> = {};
  if (forceRefresh) {
    params.force_refresh = true;
  }
  const response = await apiClient.get<CouponsListResponse>(`/bonds/${secid}/coupons`, { params });
  return response.data;
};

/**
 * Fetch coupons for multiple bonds by SECID list (batch request)
 * This is the unified method for loading coupons - supports both single and multiple bonds
 * @param secids Array of Security IDs (can be single element or multiple)
 * @param forceRefresh If true, force refresh from MOEX API (only for single bond requests)
 * @returns Map of secid to CouponsListResponse for easy lookup
 */
export const fetchBondsCoupons = async (
  secids: string[],
  forceRefresh: boolean = false
): Promise<Map<string, CouponsListResponse>> => {
  if (!secids || secids.length === 0) {
    return new Map();
  }

  // Remove duplicates and empty strings
  const uniqueSecids = Array.from(new Set(secids.filter(s => s && s.trim())));

  if (uniqueSecids.length === 0) {
    return new Map();
  }

  // For single bond, use the original endpoint for backward compatibility
  if (uniqueSecids.length === 1) {
    const secid = uniqueSecids[0];
    const response = await fetchBondCoupons(secid, forceRefresh);
    const result = new Map<string, CouponsListResponse>();
    result.set(secid, response);
    return result;
  }

  // For multiple bonds, use batch endpoint
  try {
    const params: Record<string, string[]> = {
      secids: uniqueSecids,
    };

    // Serialize array parameters correctly for FastAPI
    const paramsSerializer = (params: Record<string, any>): string => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          value.forEach((item) => {
            searchParams.append(key, String(item));
          });
        } else {
          searchParams.append(key, String(value));
        }
      });
      return searchParams.toString();
    };

    const response = await apiClient.get<MultipleCouponsResponse>('/bonds/coupons/batch', {
      params,
      paramsSerializer,
    });

    // Convert response to Map for easy lookup
    const result = new Map<string, CouponsListResponse>();
    response.data.data.forEach((item) => {
      result.set(item.secid, { coupons: item.coupons });
    });

    uniqueSecids.forEach((secid) => {
      if (!result.has(secid)) {
        result.set(secid, { coupons: [] });
      }
    });

    return result;
  } catch (error) {
    console.error('[Bonds API] Error fetching coupons batch:', error);
    throw error;
  }
};
