import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { apiClient } from '../api/client';
import { AdminCapabilitiesContext } from './adminCapabilitiesContext';
import {
  AUTH_CAPABILITIES_CHANGED_EVENT,
  getStoredAdminCapabilities,
  isAuthenticated,
  NO_ADMIN_CAPABILITIES,
  saveAdminCapabilities,
  type AdminCapabilities,
} from '../utils/auth';

type AdminCapabilitiesProviderProps = {
  children: ReactNode;
};

export function AdminCapabilitiesProvider({ children }: AdminCapabilitiesProviderProps) {
  const [capabilities, setCapabilities] = useState(NO_ADMIN_CAPABILITIES);

  const refreshCapabilities = useCallback(async () => {
    if (!isAuthenticated()) {
      setCapabilities(saveAdminCapabilities(NO_ADMIN_CAPABILITIES));
      return;
    }

    try {
      const { data } = await apiClient.get<{ capabilities?: Partial<AdminCapabilities> }>('/auth/me');
      setCapabilities(saveAdminCapabilities(data.capabilities));
    } catch {
      // Hide administrator controls when the server cannot confirm capabilities.
      setCapabilities(saveAdminCapabilities(NO_ADMIN_CAPABILITIES));
    }
  }, []);

  useEffect(() => {
    const syncStoredCapabilities = () => setCapabilities(getStoredAdminCapabilities());
    void refreshCapabilities();
    window.addEventListener(AUTH_CAPABILITIES_CHANGED_EVENT, syncStoredCapabilities);
    window.addEventListener('focus', refreshCapabilities);
    return () => {
      window.removeEventListener(AUTH_CAPABILITIES_CHANGED_EVENT, syncStoredCapabilities);
      window.removeEventListener('focus', refreshCapabilities);
    };
  }, [refreshCapabilities]);

  return (
    <AdminCapabilitiesContext.Provider value={capabilities}>
      {children}
    </AdminCapabilitiesContext.Provider>
  );
}
