import type { ZerocuponRecord } from '../api/zerocupon';

/**
 * Extract numeric term (in years) from field name like "Срок 1.0 лет"
 */
const extractTermFromField = (fieldName: string): number | null => {
  const match = fieldName.match(/Срок\s+(\d+(?:\.\d+)?)\s+лет/);
  if (!match) return null;
  return parseFloat(match[1]);
};

/**
 * Get the latest zero-coupon yield curve record
 */
export const getLatestZerocuponRecord = (records: ZerocuponRecord[]): ZerocuponRecord | null => {
  if (records.length === 0) return null;
  
  // Sort by date and time (most recent first)
  const sorted = [...records].sort((a, b) => {
    const dateA = a.Дата || '';
    const dateB = b.Дата || '';
    if (dateA !== dateB) {
      return dateB.localeCompare(dateA); // Descending order
    }
    const timeA = a.Время || '';
    const timeB = b.Время || '';
    return timeB.localeCompare(timeA); // Descending order
  });
  
  return sorted[0];
};

/**
 * Build a map of term (years) -> yield from zerocupon record
 */
export const buildYieldCurveMap = (record: ZerocuponRecord): Map<number, number> => {
  const curveMap = new Map<number, number>();
  
  // Iterate through all fields except Дата and Время
  Object.keys(record).forEach((fieldName) => {
    if (fieldName === 'Дата' || fieldName === 'Время') return;
    
    const term = extractTermFromField(fieldName);
    if (term === null) return;
    
    const value = record[fieldName];
    if (value === null || value === undefined || value === '') return;
    
    // Parse value (can be string or number)
    let yieldValue: number;
    if (typeof value === 'string') {
      const cleaned = value.trim().replace(',', '.');
      yieldValue = parseFloat(cleaned);
    } else {
      yieldValue = value;
    }
    
    if (!isNaN(yieldValue)) {
      curveMap.set(term, yieldValue);
    }
  });
  
  return curveMap;
};

/**
 * Find two neighboring terms for interpolation
 * Returns [lowerTerm, upperTerm, lowerYield, upperYield] or null if not found
 */
const findNeighboringTerms = (
  curveMap: Map<number, number>,
  horizon: number
): [number, number, number, number] | null => {
  const terms = Array.from(curveMap.keys()).sort((a, b) => a - b);
  
  // If horizon matches exactly, return that term
  if (curveMap.has(horizon)) {
    const yieldValue = curveMap.get(horizon)!;
    return [horizon, horizon, yieldValue, yieldValue];
  }
  
  // Find lower and upper bounds
  let lowerTerm: number | null = null;
  let upperTerm: number | null = null;
  
  for (let i = 0; i < terms.length; i++) {
    if (terms[i] < horizon) {
      lowerTerm = terms[i];
    } else if (terms[i] > horizon) {
      upperTerm = terms[i];
      break;
    }
  }
  
  // If no lower term found, use the smallest term
  if (lowerTerm === null && terms.length > 0) {
    lowerTerm = terms[0];
  }
  
  // If no upper term found, use the largest term
  if (upperTerm === null && terms.length > 0) {
    upperTerm = terms[terms.length - 1];
  }
  
  if (lowerTerm === null || upperTerm === null) {
    return null;
  }
  
  const lowerYield = curveMap.get(lowerTerm)!;
  const upperYield = curveMap.get(upperTerm)!;
  
  return [lowerTerm, upperTerm, lowerYield, upperYield];
};

/**
 * Interpolate zero-coupon yield for a given horizon (in years)
 * Returns null if interpolation is not possible
 */
export const interpolateZeroCurveYield = (
  curveMap: Map<number, number>,
  horizon: number
): number | null => {
  if (curveMap.size === 0) return null;
  
  // If horizon matches exactly, return that value
  if (curveMap.has(horizon)) {
    return curveMap.get(horizon)!;
  }
  
  const neighbors = findNeighboringTerms(curveMap, horizon);
  if (!neighbors) return null;
  
  const [lowerTerm, upperTerm, lowerYield, upperYield] = neighbors;
  
  // If lower and upper are the same, return that value
  if (lowerTerm === upperTerm) {
    return lowerYield;
  }
  
  // Linear interpolation
  // ZeroCurveYield = YieldLower + (YieldUpper - YieldLower) * ((Horizon - LowerTerm) / (UpperTerm - LowerTerm))
  const zeroCurveYield =
    lowerYield + (upperYield - lowerYield) * ((horizon - lowerTerm) / (upperTerm - lowerTerm));
  
  // Round to 2 decimal places
  return Math.round(zeroCurveYield * 100) / 100;
};

/**
 * Calculate spread (premium/discount) relative to zero-coupon yield curve
 * Spread = YTM - ZeroCurveYield
 * Returns null if calculation is not possible
 */
export const calculateSpread = (
  ytm: number | null | undefined,
  zeroCurveYield: number | null
): number | null => {
  if (ytm === null || ytm === undefined || isNaN(ytm)) return null;
  if (zeroCurveYield === null || isNaN(zeroCurveYield)) return null;
  
  const spread = ytm - zeroCurveYield;
  
  // Round to 2 decimal places
  return Math.round(spread * 100) / 100;
};

/**
 * Format spread as "+X.XX%" or "-X.XX%" or "0.00%"
 */
export const formatSpread = (spread: number | null): string => {
  if (spread === null || isNaN(spread)) return '—';
  
  const rounded = Math.round(spread * 100) / 100;
  
  if (rounded === 0) {
    return '0.00%';
  }
  
  const sign = rounded >= 0 ? '+' : '';
  return `${sign}${rounded.toFixed(2)}%`;
};

