import { create } from 'zustand';
import type { BondFilters, FilterOptions } from '../types/filters';

interface FiltersState {
  // Current filter values
  filters: BondFilters;
  
  // Available options for dropdowns
  filterOptions: FilterOptions | null;
  
  // Actions
  setFilter: <K extends keyof BondFilters>(
    key: K, 
    value: BondFilters[K]
  ) => void;
  setFilters: (filters: Partial<BondFilters>) => void;
  resetFilters: () => void;
  setFilterOptions: (options: FilterOptions) => void;
}

const initialFilters: BondFilters = {
  couponMin: null,
  couponMax: null,
  matdateFrom: null,
  matdateTo: null,
  listlevel: [],
  faceunit: [],
  search: '',
  skip: 0,
  limit: 100,
};

export const useFiltersStore = create<FiltersState>((set) => ({
  filters: initialFilters,
  filterOptions: null,
  
  setFilter: (key, value) => set((state) => ({
    filters: {
      ...state.filters,
      [key]: value,
      skip: key !== 'skip' ? 0 : value,  // Reset pagination on filter change
    },
  })),
  
  setFilters: (newFilters) => set((state) => ({
    filters: {
      ...state.filters,
      ...newFilters,
    },
  })),
  
  resetFilters: () => set({ 
    filters: initialFilters 
  }),
  
  setFilterOptions: (options) => set({ 
    filterOptions: options 
  }),
}));
