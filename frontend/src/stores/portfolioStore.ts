import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { BondListItem } from '../types/bond';

interface PortfolioState {
  // Portfolio bonds stored as array
  portfolioBonds: BondListItem[];
  
  // Actions
  addBondToPortfolio: (bond: BondListItem) => void;
  removeBondFromPortfolio: (secid: string) => void;
  isInPortfolio: (secid: string) => boolean;
  getPortfolioBonds: () => BondListItem[];
  clearPortfolio: () => void;
  loadBondsToPortfolio: (bonds: BondListItem[]) => void;
}

export const usePortfolioStore = create<PortfolioState>()(
  persist(
    (set, get) => ({
      portfolioBonds: [],

      addBondToPortfolio: (bond) => {
        set((state) => {
          // Check if bond already exists in portfolio
          if (state.portfolioBonds.some(b => b.SECID === bond.SECID)) {
            return state;
          }
          return {
            portfolioBonds: [...state.portfolioBonds, bond],
          };
        });
      },

      removeBondFromPortfolio: (secid) => {
        set((state) => {
          return {
            portfolioBonds: state.portfolioBonds.filter(b => b.SECID !== secid),
          };
        });
      },

      isInPortfolio: (secid) => {
        return get().portfolioBonds.some(b => b.SECID === secid);
      },

      getPortfolioBonds: () => {
        return get().portfolioBonds;
      },

      clearPortfolio: () => {
        set({ portfolioBonds: [] });
      },

      loadBondsToPortfolio: (bonds) => {
        set((state) => {
          // Create a map of existing bonds by SECID
          const existingBondsMap = new Map(state.portfolioBonds.map(b => [b.SECID, b]));
          
          // Add new bonds, avoiding duplicates
          const newBonds = bonds.filter(bond => !existingBondsMap.has(bond.SECID));
          
          return {
            portfolioBonds: [...state.portfolioBonds, ...newBonds],
          };
        });
      },
    }),
    {
      name: 'bonds-portfolio-storage',
    }
  )
);
