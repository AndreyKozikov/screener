import { apiClient } from './client';
import type { BondsListResponse } from '../types/api';
import type { BondDetail } from '../types/bond';
import type { BondFloatParamsDTO } from '../types/bondFloatParams';
import type { BondFilters } from '../types/filters';
import type { CouponsListResponse, MultipleCouponsResponse } from '../types/coupon';

/**
 * Fetch filtered bonds list
 * Loads ALL filtered data in one request for client-side pagination and search
 * Search filtering is done on client side, not sent to server
 * @param excludeSpob If true, exclude bonds with trading mode SPOB
 */
export const fetchBonds = async (filters: BondFilters, emitentTitle?: string, excludeSpob?: boolean): Promise<BondsListResponse> => {
    // Формируем payload в соответствии со схемой BondsListFiltersDTO на бэкенде
    const payload = {
        coupon_min: filters.couponMin,
        coupon_max: filters.couponMax,
        yield_min: filters.yieldMin,
        yield_max: filters.yieldMax,
        coupon_yield_min: filters.couponYieldMin,
        coupon_yield_max: filters.couponYieldMax,
        matdate_from: filters.matdateFrom || null,
        matdate_to: filters.matdateTo || null,
        listlevel: filters.listlevel && filters.listlevel.length > 0 ? filters.listlevel : null,
        faceunit: filters.faceunit && filters.faceunit.length > 0 ? filters.faceunit : null,
        bondtype: filters.bondtype && filters.bondtype.length > 0 ? filters.bondtype : null,
        bondtype43: filters.bondtype43 && filters.bondtype43.length > 0 ? filters.bondtype43 : null,
        rating_min: filters.ratingMin,
        rating_max: filters.ratingMax,
        emitent_title: emitentTitle || null,
        exclude_spob: excludeSpob === false,
        skip: 0,
        limit: 1000
    };

    console.log('[Bonds API] Fetching bonds with payload DTO:', payload);

    let response;
    try {
        const endpoint = '/bonds/';
        console.log('[Bonds API] Making request to:', apiClient.defaults.baseURL + endpoint);

        // Передаем данные в теле POST-запроса
        response = await apiClient.post<BondsListResponse>(endpoint, payload);

        console.log('[Bonds API] Response received:', response.status, response.data ? 'data OK' : 'no data');
    } catch (error) {
        console.error('[Bonds API] Error fetching bonds:', error);
        throw error;
    }

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
 * Точка графика истории цены облигации
 */
export interface BondPriceHistoryPoint {
    date: string;
    open: number | null;
}

/**
 * Ответ API истории цены облигации
 */
export interface BondPriceHistoryResponse {
    secid: string;
    data: BondPriceHistoryPoint[];
}

/**
 * Загружает историю цен для графика.
 */
export const fetchPriceHistory = async (secid: string): Promise<BondPriceHistoryResponse> => {
    const response = await apiClient.get<BondPriceHistoryResponse>(`/bonds/${secid}/price-history`);
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
/**
 * Fetch float params for a single bond by SECID.
 * GET /bonds/{secid}/float-params
 */
export const fetchFloatParamsBySecid = async (secid: string): Promise<BondFloatParamsDTO> => {
    const response = await apiClient.get<BondFloatParamsDTO>(`/bonds/${secid}/float-params`);
    return response.data;
};

/**
 * Fetch all SECIDs that have floater parameters (is_find != 0).
 * GET /bonds/float-params/secids
 */
export const fetchFloaterSecids = async (): Promise<string[]> => {
    const response = await apiClient.get<string[]>('/bonds/float-params/secids');
    return response.data;
};

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

export interface BondChatResponse {
    query: string;
    answer: string;
}

/**
 * Send a question about a bond to the LLM (Vector Retrieval + LLM)
 */
export const askBondQuestion = async (
    secid: string,
    query: string,
    model?: string,
    embeddingModel?: string
): Promise<BondChatResponse> => {
    const MODEL_TO_PROVIDER: Record<string, string> = {
        'Автоматический выбор доступной модели': '',
        'gemini-2.5-flash-lite': 'gemini',
        'gemini-2.5-flash': 'gemini-flash',
        'gemini-2.5-pro': 'gemini-2.5-pro',
        'gemini-2.0-flash': 'gemini-2-flash',
        'gemini-3-flash-preview': 'gemini-3-flash',
        'gemini-3.1-pro-preview': 'gemini-3.1-pro',
        'openrouter/deepseek-v4-pro': 'openrouter',
    };

    const providerName = model ? MODEL_TO_PROVIDER[model] : undefined;

    const response = await apiClient.post<BondChatResponse>(
        '/llm/bond-context',
        {
            secid,
            query,
            use_local_events: true,
            provider: providerName,
            embedding_model: embeddingModel,
        },
        {
            timeout: 500000 //  для генерации ответа LLM
        });
    return response.data;
};
