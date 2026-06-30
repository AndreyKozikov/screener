import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AppSettings } from '../types/settings';
import { DEFAULT_SETTINGS } from '../types/settings';

interface SettingsState {
  settings: AppSettings;
  updateSettings: (partial: Partial<AppSettings>) => void;
  resetSettings: () => void;
}

/**
 * Global settings store.
 * Persists to localStorage under the key 'app-settings'.
 */
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: { ...DEFAULT_SETTINGS },

      updateSettings: (partial) =>
        set((state) => ({
          settings: { ...state.settings, ...partial },
        })),

      resetSettings: () =>
        set({ settings: { ...DEFAULT_SETTINGS } }),
    }),
    {
      name: 'app-settings',
    }
  )
);
