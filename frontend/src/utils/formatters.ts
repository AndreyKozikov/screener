/**
 * Utility functions for formatting data for display
 */

/**
 * Format date string to localized format
 * @param dateStr - ISO date string (YYYY-MM-DD)
 * @param locale - Locale for formatting (default: 'ru-RU')
 * @returns Formatted date string or '-' if invalid
 */
export const formatDate = (dateStr: string | null, locale: string = 'ru-RU'): string => {
  if (!dateStr) return '-';
  
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '-';
    
    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '-';
  }
};

/**
 * Format number with thousands separator
 * @param value - Number to format
 * @param decimals - Number of decimal places (default: 2)
 * @param locale - Locale for formatting (default: 'ru-RU')
 * @returns Formatted number string or '-' if invalid
 */
export const formatNumber = (
  value: number | null | undefined,
  decimals: number = 2,
  locale: string = 'ru-RU'
): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  return value.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

/**
 * Format percentage value
 * @param value - Number to format as percentage
 * @param decimals - Number of decimal places (default: 2)
 * @param locale - Locale for formatting (default: 'ru-RU')
 * @returns Formatted percentage string or '-' if invalid
 */
export const formatPercent = (
  value: number | null | undefined,
  decimals: number = 2,
  locale: string = 'ru-RU'
): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  return `${value.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}%`;
};

/**
 * Format currency value
 * @param value - Number to format as currency
 * @param currency - Currency code (default: 'RUB')
 * @param locale - Locale for formatting (default: 'ru-RU')
 * @returns Formatted currency string or '-' if invalid
 */
export const formatCurrency = (
  value: number | null | undefined,
  currency: string = 'RUB',
  locale: string = 'ru-RU'
): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  return value.toLocaleString(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

/**
 * Format large numbers with K/M/B suffixes
 * @param value - Number to format
 * @param decimals - Number of decimal places (default: 1)
 * @returns Formatted string with suffix or '-' if invalid
 */
export const formatCompactNumber = (
  value: number | null | undefined,
  decimals: number = 1
): string => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  if (Math.abs(value) >= 1e9) {
    return `${(value / 1e9).toFixed(decimals)}B`;
  }
  if (Math.abs(value) >= 1e6) {
    return `${(value / 1e6).toFixed(decimals)}M`;
  }
  if (Math.abs(value) >= 1e3) {
    return `${(value / 1e3).toFixed(decimals)}K`;
  }
  return value.toFixed(decimals);
};

/**
 * Format bond status code to human-readable text
 * @param status - Status code (A, N, etc.)
 * @returns Human-readable status
 */
export const formatBondStatus = (status: string | null): string => {
  if (!status) return '-';
  
  const statusMap: Record<string, string> = {
    'A': 'Активен',
    'N': 'Неактивен',
    'S': 'Приостановлен',
    'D': 'Погашен',
  };
  
  return statusMap[status] || status;
};

/**
 * Format trading status code to human-readable text
 * @param status - Trading status code
 * @returns Human-readable trading status
 */
export const formatTradingStatus = (status: string | null): string => {
  if (!status) return '-';
  
  const statusMap: Record<string, string> = {
    'N': 'Не торгуется',
    'S': 'Торгуется',
    'D': 'Делистинг',
  };
  
  return statusMap[status] || status;
};

/**
 * Truncate text to specified length with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text
 */
export const truncateText = (text: string, maxLength: number = 50): string => {
  if (!text || text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
};

/**
 * Calculate days until maturity
 * @param matDate - Maturity date string (YYYY-MM-DD)
 * @returns Number of days or null if invalid
 */
export const daysUntilMaturity = (matDate: string | null): number | null => {
  if (!matDate) return null;
  
  try {
    const today = new Date();
    const maturity = new Date(matDate);
    if (isNaN(maturity.getTime())) return null;
    
    const diffTime = maturity.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return diffDays;
  } catch {
    return null;
  }
};

/**
 * Format days until maturity to human-readable text
 * @param matDate - Maturity date string
 * @returns Formatted text like "123 дня" or "Погашена"
 */
export const formatDaysToMaturity = (matDate: string | null): string => {
  const days = daysUntilMaturity(matDate);
  
  if (days === null) return '-';
  if (days < 0) return 'Погашена';
  if (days === 0) return 'Сегодня';
  if (days === 1) return '1 день';
  
  // Russian pluralization
  const lastDigit = days % 10;
  const lastTwoDigits = days % 100;
  
  if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
    return `${days} дней`;
  }
  if (lastDigit === 1) {
    return `${days} день`;
  }
  if (lastDigit >= 2 && lastDigit <= 4) {
    return `${days} дня`;
  }
  return `${days} дней`;
};

/**
 * Calculate coupon yield to current price
 * @param couponPercent - Coupon rate in percent
 * @param currentPrice - Current price in percent of face value
 * @returns Coupon yield to current price in percent
 */
export const calculateCouponYieldToPrice = (
  couponPercent: number | null,
  currentPrice: number | null
): number | null => {
  if (couponPercent === null || currentPrice === null || currentPrice === 0) {
    return null;
  }
  
  // Current price is in percent of face value (e.g., 95.5 means 95.5%)
  // Coupon percent is annual coupon rate (e.g., 7.5 means 7.5% per year)
  // Yield to current price = (Coupon % / Current Price %) * 100
  return (couponPercent / currentPrice) * 100;
};

/**
 * Calculate coupon frequency from period in days
 * @param couponPeriod - Coupon period in days
 * @returns Frequency per year (integer) or null
 */
export const calculateCouponFrequency = (couponPeriod: number | null): number | null => {
  if (couponPeriod === null || couponPeriod === 0) return null;
  
  // Approximate days in a year
  const daysInYear = 365;
  const frequency = daysInYear / couponPeriod;
  
  // Round to nearest integer
  return Math.round(frequency);
};