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
          // Check if bond already exists in comparison by SECID
          if (state.comparisonBonds.some(b => b.SECID === bond.SECID)) {
            return state;
          }
          
          // Check if bond already exists by ISIN (if ISIN exists)
          // Some bonds like OFZ may have multiple SECIDs but same ISIN
          if (bond.ISIN && bond.ISIN.trim() !== '') {
            const isin = bond.ISIN.trim();
            if (state.comparisonBonds.some(b => b.ISIN && b.ISIN.trim() === isin)) {
              return state;
            }
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
          // Create maps of existing bonds by SECID and ISIN
          const existingBondsBySecid = new Map(state.comparisonBonds.map(b => [b.SECID, b]));
          const existingBondsByIsin = new Map<string, BondListItem>();
          
          // Build ISIN map for existing bonds (only for bonds with ISIN)
          for (const bond of state.comparisonBonds) {
            if (bond.ISIN && bond.ISIN.trim() !== '') {
              const isin = bond.ISIN.trim();
              if (!existingBondsByIsin.has(isin)) {
                existingBondsByIsin.set(isin, bond);
              }
            }
          }
          
          // Remove duplicates from incoming bonds array by ISIN (if ISIN exists)
          // Some bonds like OFZ may have multiple SECIDs but same ISIN
          const uniqueBondsMap = new Map<string, BondListItem>();
          const seenIsins = new Set<string>();
          
          for (const bond of bonds) {
            // If bond has ISIN, use it for deduplication
            if (bond.ISIN && bond.ISIN.trim() !== '') {
              const isin = bond.ISIN.trim();
              if (!seenIsins.has(isin)) {
                seenIsins.add(isin);
                uniqueBondsMap.set(bond.SECID, bond);
              }
              // If ISIN already seen, skip this bond (it's a duplicate)
            } else {
              // If no ISIN, use SECID for deduplication (fallback)
              if (!uniqueBondsMap.has(bond.SECID)) {
                uniqueBondsMap.set(bond.SECID, bond);
              }
            }
          }
          
          // Filter out bonds that already exist (by SECID or ISIN)
          const newBonds = Array.from(uniqueBondsMap.values()).filter(bond => {
            // Check by SECID first
            if (existingBondsBySecid.has(bond.SECID)) {
              return false;
            }
            
            // Check by ISIN if ISIN exists
            if (bond.ISIN && bond.ISIN.trim() !== '') {
              const isin = bond.ISIN.trim();
              if (existingBondsByIsin.has(isin)) {
                return false;
              }
            }
            
            return true;
          });
          
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

