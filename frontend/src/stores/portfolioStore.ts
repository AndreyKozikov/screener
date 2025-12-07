import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { BondListItem, PortfolioBond } from '../types/bond';

interface PortfolioState {
  // Portfolio bonds stored as array with quantity
  portfolioBonds: PortfolioBond[];
  
  // Actions
  addBondToPortfolio: (bond: BondListItem) => void;
  removeBondFromPortfolio: (secid: string) => void;
  isInPortfolio: (secid: string) => boolean;
  getPortfolioBonds: () => PortfolioBond[];
  clearPortfolio: () => void;
  loadBondsToPortfolio: (bonds: BondListItem[]) => void;
  loadPortfolioBonds: (bonds: PortfolioBond[]) => void;
  updateBondQuantity: (secid: string, quantity: number) => void;
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
          // Add bond with default quantity of 1
          const portfolioBond: PortfolioBond = {
            ...bond,
            quantity: 1,
          };
          return {
            portfolioBonds: [...state.portfolioBonds, portfolioBond],
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
          
          // Add new bonds, avoiding duplicates, with default quantity of 1
          const newBonds: PortfolioBond[] = bonds
            .filter(bond => !existingBondsMap.has(bond.SECID))
            .map(bond => ({
              ...bond,
              quantity: 1,
            }));
          
          return {
            portfolioBonds: [...state.portfolioBonds, ...newBonds],
          };
        });
      },

      loadPortfolioBonds: (bonds) => {
        set((state) => {
          // Create a map of existing bonds by SECID
          const existingBondsMap = new Map(state.portfolioBonds.map(b => [b.SECID, b]));
          
          // Add new bonds, avoiding duplicates, preserving quantities from import
          const newBonds: PortfolioBond[] = bonds
            .filter(bond => !existingBondsMap.has(bond.SECID))
            .map(bond => ({
              ...bond,
              quantity: bond.quantity ?? 1, // Preserve quantity from import or default to 1
            }));
          
          return {
            portfolioBonds: [...state.portfolioBonds, ...newBonds],
          };
        });
      },

      updateBondQuantity: (secid, quantity) => {
        set((state) => {
          // Validate quantity: must be integer > 0
          const validQuantity = Math.max(1, Math.floor(quantity));
          
          return {
            portfolioBonds: state.portfolioBonds.map(bond =>
              bond.SECID === secid
                ? { ...bond, quantity: validQuantity }
                : bond
            ),
          };
        });
      },
    }),
    {
      name: 'bonds-portfolio-storage',
    }
  )
);
