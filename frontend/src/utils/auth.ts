export const AUTH_TOKEN_STORAGE_KEY = 'bonds-access-token';
export const AUTH_EMAIL_STORAGE_KEY = 'bonds-user-email';
const AUTH_REFRESH_DATA_CAPABILITY_KEY = 'bonds-capability-refresh-data';
const AUTH_MANAGE_SETTINGS_CAPABILITY_KEY = 'bonds-capability-manage-settings';
export const AUTH_CAPABILITIES_CHANGED_EVENT = 'bonds:auth-capabilities-changed';

export const PORTFOLIO_AUTH_REDIRECT_STATE = { from: 'portfolio' } as const;

export type AdminCapabilities = {
  refresh_data: boolean;
  manage_settings: boolean;
};

export const NO_ADMIN_CAPABILITIES: AdminCapabilities = {
  refresh_data: false,
  manage_settings: false,
};

const normalizeCapabilities = (value?: Partial<AdminCapabilities> | null): AdminCapabilities => ({
  refresh_data: value?.refresh_data === true,
  manage_settings: value?.manage_settings === true,
});

export const getStoredAdminCapabilities = (): AdminCapabilities => {
  if (typeof window === 'undefined') return NO_ADMIN_CAPABILITIES;
  return {
    refresh_data: window.localStorage.getItem(AUTH_REFRESH_DATA_CAPABILITY_KEY) === 'true',
    manage_settings: window.localStorage.getItem(AUTH_MANAGE_SETTINGS_CAPABILITY_KEY) === 'true',
  };
};

export const saveAdminCapabilities = (value?: Partial<AdminCapabilities> | null): AdminCapabilities => {
  const capabilities = normalizeCapabilities(value);
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(AUTH_REFRESH_DATA_CAPABILITY_KEY, String(capabilities.refresh_data));
    window.localStorage.setItem(AUTH_MANAGE_SETTINGS_CAPABILITY_KEY, String(capabilities.manage_settings));
    window.localStorage.removeItem('bonds-user-role');
    window.dispatchEvent(new Event(AUTH_CAPABILITIES_CHANGED_EVENT));
  }
  return capabilities;
};

const readStoredToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
};

const isTokenExpired = (token: string): boolean => {
  const payload = token.split('.')[1];
  if (!payload) return true;

  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
    const claims = JSON.parse(window.atob(padded)) as { exp?: unknown };
    return typeof claims.exp !== 'number' || claims.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
};

export const isAuthenticated = (): boolean => {
  const token = readStoredToken();
  return Boolean(token) && !isTokenExpired(token as string);
};

export const saveAuthSession = (
  token: string,
  email: string,
  capabilities?: Partial<AdminCapabilities> | null,
): void => {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  window.localStorage.setItem(AUTH_EMAIL_STORAGE_KEY, email);
  saveAdminCapabilities(capabilities);
};

export const clearAuthSession = (): void => {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(AUTH_EMAIL_STORAGE_KEY);
  window.localStorage.removeItem('bonds-screener:agent');
  saveAdminCapabilities(NO_ADMIN_CAPABILITIES);
};
