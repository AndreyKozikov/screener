export const AUTH_TOKEN_STORAGE_KEY = 'bonds-access-token';
export const AUTH_EMAIL_STORAGE_KEY = 'bonds-user-email';

export const PORTFOLIO_AUTH_REDIRECT_STATE = { from: 'portfolio' } as const;

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

export const saveAuthSession = (token: string, email: string): void => {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  window.localStorage.setItem(AUTH_EMAIL_STORAGE_KEY, email);
};

export const clearAuthSession = (): void => {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(AUTH_EMAIL_STORAGE_KEY);
};
