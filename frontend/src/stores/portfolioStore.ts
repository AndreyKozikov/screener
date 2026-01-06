import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { BondListItem, PortfolioBond } from '../types/bond';
import type { Coupon } from '../types/coupon';
import { fetchBondCoupons } from '../api/bonds';

interface PortfolioState {
  // Portfolio bonds stored as array with quantity
  portfolioBonds: PortfolioBond[];
  
  // Coupons data by SECID
  couponsBySecid: Record<string, Coupon[]>;
  
  // Actions
  addBondToPortfolio: (bond: BondListItem) => void;
  removeBondFromPortfolio: (secid: string) => void;
  isInPortfolio: (secid: string) => boolean;
  getPortfolioBonds: () => PortfolioBond[];
  clearPortfolio: () => void;
  loadBondsToPortfolio: (bonds: BondListItem[]) => void;
  loadPortfolioBonds: (bonds: PortfolioBond[]) => void;
  updateBondQuantity: (secid: string, quantity: number) => void;
  setCouponsForBond: (secid: string, coupons: Coupon[]) => void;
  removeCouponsForBond: (secid: string) => void;
  getNextPaymentDate: () => Date | null;
}

export const usePortfolioStore = create<PortfolioState>()(
  persist(
    (set, get) => ({
      portfolioBonds: [],
      couponsBySecid: {},

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
          
          // Load coupons asynchronously
          fetchBondCoupons(bond.SECID)
            .then((response) => {
              get().setCouponsForBond(bond.SECID, response.coupons || []);
            })
            .catch((err) => {
              console.error(`Failed to load coupons for ${bond.SECID}:`, err);
            });
          
          return {
            portfolioBonds: [...state.portfolioBonds, portfolioBond],
          };
        });
      },

      removeBondFromPortfolio: (secid) => {
        set((state) => {
          const { [secid]: removed, ...remainingCoupons } = state.couponsBySecid;
          return {
            portfolioBonds: state.portfolioBonds.filter(b => b.SECID !== secid),
            couponsBySecid: remainingCoupons,
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
        set({ portfolioBonds: [], couponsBySecid: {} });
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
          
          // Remove duplicates from incoming bonds array (keep first occurrence)
          const uniqueBondsMap = new Map<string, PortfolioBond>();
          for (const bond of bonds) {
            if (!uniqueBondsMap.has(bond.SECID)) {
              uniqueBondsMap.set(bond.SECID, bond);
            }
          }
          
          // Add new bonds, avoiding duplicates with existing portfolio, preserving quantities from import
          const newBonds: PortfolioBond[] = Array.from(uniqueBondsMap.values())
            .filter(bond => !existingBondsMap.has(bond.SECID))
            .map(bond => ({
              ...bond,
              quantity: bond.quantity ?? 1, // Preserve quantity from import or default to 1
            }));
          
          // Load coupons for all new bonds asynchronously
          const couponsPromises = newBonds.map((bond) =>
            fetchBondCoupons(bond.SECID)
              .then((response) => {
                get().setCouponsForBond(bond.SECID, response.coupons || []);
              })
              .catch((err) => {
                console.error(`Failed to load coupons for ${bond.SECID}:`, err);
              })
          );
          
          // Don't wait for coupons to load - they'll be set asynchronously
          Promise.all(couponsPromises).catch((err) => {
            console.error('Error loading coupons for portfolio:', err);
          });
          
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

      setCouponsForBond: (secid, coupons) => {
        set((state) => {
          return {
            couponsBySecid: {
              ...state.couponsBySecid,
              [secid]: coupons,
            },
          };
        });
      },

      removeCouponsForBond: (secid) => {
        set((state) => {
          const { [secid]: removed, ...remainingCoupons } = state.couponsBySecid;
          return {
            couponsBySecid: remainingCoupons,
          };
        });
      },

      getNextPaymentDate: () => {
        const state = get();
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        today.setMinutes(0, 0);
        today.setSeconds(0, 0);
        today.setMilliseconds(0);
        
        let nearestDate: Date | null = null;
        
        // Check all bonds in portfolio
        for (const bond of state.portfolioBonds) {
          const coupons = state.couponsBySecid[bond.SECID] || [];
          
          // Check coupon payments
          for (const coupon of coupons) {
            if (coupon.coupondate) {
              // Parse date string (YYYY-MM-DD format)
              const dateStr = coupon.coupondate;
              const [year, month, day] = dateStr.split('-').map(Number);
              const couponDate = new Date(year, month - 1, day);
              couponDate.setHours(0, 0, 0, 0);
              
              // Only include future dates (strictly greater than today)
              if (couponDate.getTime() > today.getTime()) {
                if (!nearestDate || couponDate.getTime() < nearestDate.getTime()) {
                  nearestDate = new Date(couponDate);
                }
              }
            }
          }
          
          // Check maturity date
          if (bond.MATDATE) {
            // Parse date string (YYYY-MM-DD format)
            const dateStr = bond.MATDATE;
            const [year, month, day] = dateStr.split('-').map(Number);
            const matDate = new Date(year, month - 1, day);
            matDate.setHours(0, 0, 0, 0);
            
            // Only include future dates (strictly greater than today)
            if (matDate.getTime() > today.getTime()) {
              if (!nearestDate || matDate.getTime() < nearestDate.getTime()) {
                nearestDate = new Date(matDate);
              }
            }
          }
        }
        
        return nearestDate;
      },
    }),
    {
      name: 'bonds-portfolio-storage',
    }
  )
);
