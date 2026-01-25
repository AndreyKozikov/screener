import { create } from 'zustand';
import type { BondFilters, FilterOptions } from '../types/filters';
import { fetchFilterOptions } from '../api/metadata';

interface FiltersState {
  // Active filters (applied to data)
  filters: BondFilters;
  
  // Draft filters (being edited but not yet applied)
  draftFilters: BondFilters;
  
  // Available options for dropdowns
  filterOptions: FilterOptions | null;
  
  // Loading and error states
  isLoadingFilterOptions: boolean;
  filterOptionsError: string | null;
  
  // Actions
  setDraftFilter: <K extends keyof BondFilters>(
    key: K, 
    value: BondFilters[K]
  ) => void;
  applyFilters: () => void;
  resetFilters: () => void;
  setFilterOptions: (options: FilterOptions) => void;
  setFilterOptionsLoading: (loading: boolean) => void;
  setFilterOptionsError: (error: string | null) => void;
  loadFilterOptions: () => Promise<void>;
  
  // Legacy action for backward compatibility
  setFilter: <K extends keyof BondFilters>(
    key: K, 
    value: BondFilters[K]
  ) => void;
  setFilters: (filters: Partial<BondFilters>) => void;
}

const initialFilters: BondFilters = {
  couponMin: null,
  couponMax: null,
  yieldMin: null,
  yieldMax: null,
  couponYieldMin: null,
  couponYieldMax: null,
  matdateFrom: null,
  matdateTo: null,
  listlevel: [],
  faceunit: [],
  bondtype: [],
  bondtype43: [],
  ratingMin: null,
  ratingMax: null,
  search: '',
  skip: 0,
  limit: 100,
};

export const useFiltersStore = create<FiltersState>((set, get) => ({
  filters: initialFilters,
  draftFilters: initialFilters,
  filterOptions: null,
  isLoadingFilterOptions: false,
  filterOptionsError: null,
  
  // Update draft filter (does not trigger data reload)
  setDraftFilter: (key, value) => set((state) => ({
    draftFilters: {
      ...state.draftFilters,
      [key]: value,
    },
  })),
  
  // Apply draft filters to active filters (triggers data reload)
  applyFilters: () => set((state) => ({
    filters: {
      ...state.draftFilters,
      skip: 0, // Reset pagination when applying filters
    },
  })),
  
  // Reset both active and draft filters
  resetFilters: () => set({ 
    filters: initialFilters,
    draftFilters: initialFilters,
  }),
  
  setFilterOptions: (options) => set({ 
    filterOptions: options,
    filterOptionsError: null,
  }),
  
  setFilterOptionsLoading: (loading) => set({ 
    isLoadingFilterOptions: loading 
  }),
  
  setFilterOptionsError: (error) => set({ 
    filterOptionsError: error 
  }),
  
  // Load filter options with error handling
  loadFilterOptions: async () => {
    const state = get();
    // Если уже загружаются или уже загружены, не загружаем повторно
    if (state.isLoadingFilterOptions || state.filterOptions) {
      return;
    }
    
    set({ isLoadingFilterOptions: true, filterOptionsError: null });
    
    try {
      const options = await fetchFilterOptions();
      set({ 
        filterOptions: options,
        isLoadingFilterOptions: false,
        filterOptionsError: null,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Не удалось загрузить опции фильтров';
      set({ 
        isLoadingFilterOptions: false,
        filterOptionsError: errorMessage,
      });
      console.error('Failed to load filter options:', error);
    }
  },
  
  // Legacy actions for backward compatibility (for search filter)
  setFilter: (key, value) => set((state) => ({
    filters: {
      ...state.filters,
      [key]: value,
      skip: key !== 'skip' ? 0 : (typeof value === 'number' ? value : state.filters.skip),
    },
  })),
  
  setFilters: (newFilters) => set((state) => ({
    filters: {
      ...state.filters,
      ...newFilters,
    },
  })),
}));
