import { create } from 'zustand';

interface UiState {
  // Selected bond for details view
  selectedBondId: string | null;
  
  // Drawer state (for mobile/responsive)
  isDrawerOpen: boolean;
  
  // Global loading states
  isInitializing: boolean;
  
  // Dataset refresh trigger
  dataRefreshVersion: number;
  
  // Actions
  setSelectedBond: (secid: string | null) => void;
  toggleDrawer: () => void;
  setDrawerOpen: (open: boolean) => void;
  setInitializing: (loading: boolean) => void;
  triggerDataRefresh: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  // Initial state
  selectedBondId: null,
  isDrawerOpen: false,
  isInitializing: true,
  dataRefreshVersion: 0,
  
  // Actions
  setSelectedBond: (secid) => set({ selectedBondId: secid }),
  
  toggleDrawer: () => set((state) => ({ 
    isDrawerOpen: !state.isDrawerOpen 
  })),
  
  setDrawerOpen: (open) => set({ isDrawerOpen: open }),
  
  setInitializing: (loading) => set({ isInitializing: loading }),
  
  triggerDataRefresh: () => set((state) => ({
    dataRefreshVersion: state.dataRefreshVersion + 1,
  })),
}));
