import { create } from 'zustand';

interface SelectedReportPortfolioState {
  portfolioId: number | null;
  setPortfolioId: (id: number | null) => void;
}

export const useSelectedReportPortfolioStore = create<SelectedReportPortfolioState>((set) => ({
  portfolioId: null,
  setPortfolioId: (portfolioId) => set({ portfolioId }),
}));
