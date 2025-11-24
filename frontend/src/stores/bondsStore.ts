import { create } from 'zustand';
import type { BondListItem } from '../types/bond';
import type { BondsListResponse } from '../types/api';

interface BondsState {
  // Data
  bonds: BondListItem[];
  totalBonds: number;
  filteredCount: number;
  
  // Loading states
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setBonds: (response: BondsListResponse) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearBonds: () => void;
}

export const useBondsStore = create<BondsState>((set) => ({
  // Initial state
  bonds: [],
  totalBonds: 0,
  filteredCount: 0,
  isLoading: false,
  error: null,
  
  // Actions
  setBonds: (response) => set({
    bonds: response.bonds,
    totalBonds: response.total,
    filteredCount: response.filtered,
    isLoading: false,
    error: null,
  }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  setError: (error) => set({ 
    error, 
    isLoading: false 
  }),
  
  clearBonds: () => set({
    bonds: [],
    totalBonds: 0,
    filteredCount: 0,
    error: null,
  }),
}));
