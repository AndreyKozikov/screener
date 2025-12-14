import { create } from 'zustand';
import type { BondFilters, FilterOptions } from '../types/filters';

interface FiltersState {
  // Active filters (applied to data)
  filters: BondFilters;
  
  // Draft filters (being edited but not yet applied)
  draftFilters: BondFilters;
  
  // Available options for dropdowns
  filterOptions: FilterOptions | null;
  
  // Actions
  setDraftFilter: <K extends keyof BondFilters>(
    key: K, 
    value: BondFilters[K]
  ) => void;
  applyFilters: () => void;
  resetFilters: () => void;
  setFilterOptions: (options: FilterOptions) => void;
  
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
  couponType: [],
  ratingMin: null,
  ratingMax: null,
  search: '',
  skip: 0,
  limit: 100,
};

export const useFiltersStore = create<FiltersState>((set) => ({
  filters: initialFilters,
  draftFilters: initialFilters,
  filterOptions: null,
  
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
    filterOptions: options 
  }),
  
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
