/**
 * Application-wide constants
 */

// API Configuration
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  TIMEOUT: 10000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000,
};

// Pagination Defaults
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 100,
  PAGE_SIZE_OPTIONS: [50, 100, 200, 500],
  MAX_PAGE_SIZE: 1000,
};

// Filter Defaults
export const FILTER_DEFAULTS = {
  COUPON_MIN: null,
  COUPON_MAX: null,
  MATDATE_FROM: null,
  MATDATE_TO: null,
  STATUS: [],
  TRADING_STATUS: [],
  BOARDID: [],
  SEARCH: '',
  SKIP: 0,
  LIMIT: 100,
};

// Bond Status Options
export const BOND_STATUS = {
  ACTIVE: 'A',
  INACTIVE: 'N',
  SUSPENDED: 'S',
  REDEEMED: 'D',
} as const;

export const BOND_STATUS_LABELS: Record<string, string> = {
  A: 'Активен',
  N: 'Неактивен',
  S: 'Приостановлен',
  D: 'Погашен',
};

// Trading Status Options
export const TRADING_STATUS = {
  NOT_TRADING: 'N',
  TRADING: 'S',
  DELISTED: 'D',
} as const;

export const TRADING_STATUS_LABELS: Record<string, string> = {
  N: 'Не торгуется',
  S: 'Торгуется',
  D: 'Делистинг',
};

// Board IDs
export const BOARD_IDS = {
  TQOB: 'TQOB', // Т+ Облигации
  TQCB: 'TQCB', // Т+ Облигации (USD)
  TQRD: 'TQRD', // Т+ Облигации (Д)
  TQIR: 'TQIR', // Т+ Облигации (ПИР)
} as const;

// Date Formats
export const DATE_FORMAT = {
  DISPLAY: 'DD.MM.YYYY',
  API: 'YYYY-MM-DD',
  FULL: 'DD.MM.YYYY HH:mm:ss',
};

// Number Formats
export const NUMBER_FORMAT = {
  DECIMALS_DEFAULT: 2,
  DECIMALS_PERCENT: 2,
  DECIMALS_CURRENCY: 2,
  DECIMALS_COMPACT: 1,
  LOCALE: 'ru-RU',
  CURRENCY: 'RUB',
};

// Chart Configuration
export const CHART_CONFIG = {
  HEIGHT: 300,
  COLORS: {
    PRIMARY: '#1976d2',
    SECONDARY: '#424242',
    SUCCESS: '#4caf50',
    ERROR: '#f44336',
    WARNING: '#ff9800',
    GRID: '#e0e0e0',
  },
  ANIMATION_DURATION: 300,
};

// Table Configuration
export const TABLE_CONFIG = {
  ROW_HEIGHT: 52,
  HEADER_HEIGHT: 56,
  MIN_COLUMN_WIDTH: 100,
  DEFAULT_COLUMN_WIDTH: 150,
};

// UI Breakpoints (matches MUI theme)
export const BREAKPOINTS = {
  XS: 0,
  SM: 600,
  MD: 900,
  LG: 1200,
  XL: 1536,
};

// Local Storage Keys
export const STORAGE_KEYS = {
  THEME_MODE: 'bondsScreener_themeMode',
  TABLE_PAGE_SIZE: 'bondsScreener_tablePageSize',
  FILTERS: 'bondsScreener_filters',
  SELECTED_COLUMNS: 'bondsScreener_selectedColumns',
  COLUMN_ORDER: 'bondsScreener_columnOrder',
};

// Error Messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Ошибка сети. Проверьте подключение к интернету.',
  SERVER_ERROR: 'Ошибка сервера. Попробуйте позже.',
  NOT_FOUND: 'Данные не найдены.',
  INVALID_REQUEST: 'Некорректный запрос.',
  TIMEOUT: 'Превышено время ожидания.',
  UNKNOWN: 'Произошла неизвестная ошибка.',
};

// Success Messages
export const SUCCESS_MESSAGES = {
  DATA_LOADED: 'Данные успешно загружены',
  EXPORT_SUCCESS: 'Данные успешно экспортированы',
};

// Loading Messages
export const LOADING_MESSAGES = {
  LOADING_BONDS: 'Загрузка облигаций...',
  LOADING_DETAILS: 'Загрузка деталей...',
  LOADING_FILTERS: 'Загрузка фильтров...',
  APPLYING_FILTERS: 'Применение фильтров...',
};

// Feature Flags (for future enhancements)
export const FEATURES = {
  ENABLE_EXPORT_CSV: true,
  ENABLE_EXPORT_JSON: true,
  ENABLE_WATCHLIST: false, // Future feature
  ENABLE_ALERTS: false,    // Future feature
  ENABLE_CHARTS: true,
};

// Column Definitions for Table
export const DEFAULT_VISIBLE_COLUMNS = [
  'SECID',
  'SHORTNAME',
  'COUPONPERCENT',
  'YIELDATPREVWAPRICE',
  'MATDATE',
  'NEXTCOUPON',
  'PREVPRICE',
  'STATUS',
];

// Refresh Intervals (milliseconds)
export const REFRESH_INTERVALS = {
  BONDS_LIST: 60000,        // 1 minute
  BOND_DETAILS: 30000,      // 30 seconds
  FILTER_OPTIONS: 300000,   // 5 minutes
};

export default {
  API_CONFIG,
  PAGINATION,
  FILTER_DEFAULTS,
  BOND_STATUS,
  BOND_STATUS_LABELS,
  TRADING_STATUS,
  TRADING_STATUS_LABELS,
  DATE_FORMAT,
  NUMBER_FORMAT,
  CHART_CONFIG,
  TABLE_CONFIG,
  BREAKPOINTS,
  STORAGE_KEYS,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  LOADING_MESSAGES,
  FEATURES,
  DEFAULT_VISIBLE_COLUMNS,
  REFRESH_INTERVALS,
};
