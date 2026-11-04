import { apiClient } from './client';

export interface SettingsOption {
  value: string;
  label: string;
}

export interface SettingsField {
  key: string;
  label: string;
  description: string;
  type: 'boolean' | 'integer' | 'number' | 'text' | 'secret' | 'select' | 'multiselect';
  value: unknown;
  default: unknown;
  options?: SettingsOption[] | null;
  restart?: boolean;
  secret?: boolean;
  is_set?: boolean | null;
  section?: string | null;
  minimum?: number | null;
  maximum?: number | null;
}

export interface SettingsGroup {
  id: string;
  title: string;
  description: string;
  fields: SettingsField[];
}

export interface SettingsSchema {
  groups: SettingsGroup[];
}

/** Загружает схему runtime-настроек бэкенда (вкладки, поля, текущие значения). */
export const fetchSettings = async (): Promise<SettingsSchema> => {
  const { data } = await apiClient.get<SettingsSchema>('/settings');
  return data;
};

/**
 * Применяет переопределения настроек бэкенда.
 * @param updates словарь «ключ настройки → значение»
 * @param resetAll если true — сбросить все переопределения к значениям из конфигурации
 */
export const updateSettings = async (
  updates: Record<string, unknown>,
  resetAll = false,
): Promise<SettingsSchema> => {
  const { data } = await apiClient.put<SettingsSchema>('/settings', {
    updates,
    reset_all: resetAll,
  });
  return data;
};
