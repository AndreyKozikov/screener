import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { BondListItem } from '../types/bond';

interface ComparisonState {
  // Comparison bonds stored as array
  comparisonBonds: BondListItem[];
  
  // Actions
  addBondToComparison: (bond: BondListItem) => void;
  removeBondFromComparison: (secid: string) => void;
  isInComparison: (secid: string) => boolean;
  getComparisonBonds: () => BondListItem[];
  clearComparison: () => void;
  loadBondsToComparison: (bonds: BondListItem[]) => void;
}

export const useComparisonStore = create<ComparisonState>()(
  persist(
    (set, get) => ({
      comparisonBonds: [],

      addBondToComparison: (bond) => {
        set((state) => {
          // Check if bond already exists in comparison
          if (state.comparisonBonds.some(b => b.SECID === bond.SECID)) {
            return state;
          }
          // Add bond to comparison
          return {
            comparisonBonds: [...state.comparisonBonds, bond],
          };
        });
      },

      removeBondFromComparison: (secid) => {
        set((state) => {
          return {
            comparisonBonds: state.comparisonBonds.filter(b => b.SECID !== secid),
          };
        });
      },

      isInComparison: (secid) => {
        return get().comparisonBonds.some(b => b.SECID === secid);
      },

      getComparisonBonds: () => {
        return get().comparisonBonds;
      },

      clearComparison: () => {
        set({ comparisonBonds: [] });
      },

      loadBondsToComparison: (bonds) => {
        set((state) => {
          // Create a map of existing bonds by SECID
          const existingBondsMap = new Map(state.comparisonBonds.map(b => [b.SECID, b]));
          
          // Add new bonds, avoiding duplicates
          const newBonds = bonds.filter(bond => !existingBondsMap.has(bond.SECID));
          
          return {
            comparisonBonds: [...state.comparisonBonds, ...newBonds],
          };
        });
      },
    }),
    {
      name: 'bonds-comparison-storage',
    }
  )
);

