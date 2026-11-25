import { create } from 'zustand';

interface UiState {
  
  // Drawer state (for mobile/responsive)
  isDrawerOpen: boolean;
  
  // Global loading states
  isInitializing: boolean;
  
  // Dataset refresh trigger
  dataRefreshVersion: number;
  refreshDialogRequested: boolean;
  
  // Actions
  toggleDrawer: () => void;
  setDrawerOpen: (open: boolean) => void;
  setInitializing: (loading: boolean) => void;
  triggerDataRefresh: () => void;
  requestRefreshDialog: () => void;
  clearRefreshDialogRequest: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  // Initial state
  isDrawerOpen: false,
  isInitializing: true,
  dataRefreshVersion: 0,
  refreshDialogRequested: false,
  
  // Actions
  
  toggleDrawer: () => set((state) => ({ 
    isDrawerOpen: !state.isDrawerOpen 
  })),
  
  setDrawerOpen: (open) => set({ isDrawerOpen: open }),
  
  setInitializing: (loading) => set({ isInitializing: loading }),
  
  triggerDataRefresh: () => set((state) => ({
    dataRefreshVersion: state.dataRefreshVersion + 1,
  })),
  requestRefreshDialog: () => set({ refreshDialogRequested: true }),
  clearRefreshDialogRequest: () => set({ refreshDialogRequested: false }),
}));



