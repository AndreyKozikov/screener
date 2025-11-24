import { fetchBondDetail, fetchBondCoupons } from '../api/bonds';
import { fetchColumnMapping, fetchDescriptions } from '../api/metadata';
import type { BondDetail, BondFieldValue } from '../types/bond';
import type { DescriptionsResponse } from '../api/metadata';
import type { Coupon } from '../types/coupon';
import { formatDate, formatNumber, formatPercent, formatBondStatus, formatTradingStatus } from './formatters';

type FieldDescriptionMap = Record<string, string>;

const isoDateRegex = /^\d{4}-\d{2}-\d{2}/;
const isoDateTimeRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:/;
const numericPattern = /^-?\d+(?:[.,]\d+)?$/;
const percentKeywords = ['PERCENT', 'YIELD', 'RATE', 'SPREAD'];
const zeroDecimalKeywords = ['SIZE', 'VOLUME', 'COUNT', 'LOT', 'NUM', 'NUMBER', 'PERIOD', 'QUANTITY'];
const currencyKeywords = ['VALUE', 'PRICE', 'AMOUNT', 'SUM', 'CAPITAL', 'COST', 'VOLTODAY', 'VALTODAY', 'WAPRICE', 'LAST', 'BID', 'OFFER'];

const formatNumericValue = (fieldUpper: string, numericValue: number): string => {
  if (!Number.isFinite(numericValue)) {
    return '-';
  }

  if (percentKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatPercent(numericValue);
  }

  if (currencyKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 2);
  }

  if (zeroDecimalKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 0);
  }

  return formatNumber(numericValue, Math.abs(numericValue) < 1 ? 4 : 2);
};

const formatFieldValue = (field: string, rawValue: BondFieldValue): string => {
  if (rawValue === null || rawValue === undefined) {
    return '—';
  }

  if (Array.isArray(rawValue)) {
    const formatted = rawValue
      .map((value) => formatFieldValue(field, value as BondFieldValue))
      .filter((value) => value !== '—');

    return formatted.length > 0 ? formatted.join(', ') : '—';
  }

  if (typeof rawValue === 'boolean') {
    return rawValue ? 'Да' : 'Нет';
  }

  const fieldUpper = field.toUpperCase();

  if (typeof rawValue === 'number') {
    return formatNumericValue(fieldUpper, rawValue);
  }

  if (typeof rawValue === 'string') {
    const trimmed = rawValue.trim();

    if (trimmed.length === 0 || trimmed.toLowerCase() === 'nan') {
      return '—';
    }

    if (fieldUpper.includes('DATE') || isoDateRegex.test(trimmed) || isoDateTimeRegex.test(trimmed)) {
      return formatDate(trimmed);
    }

    if (numericPattern.test(trimmed)) {
      const parsed = Number(trimmed.replace(',', '.'));
      return formatNumericValue(fieldUpper, parsed);
    }

    return trimmed;
  }

  return String(rawValue);
};

const flattenDescriptions = (descriptions: DescriptionsResponse): FieldDescriptionMap => {
  const result: FieldDescriptionMap = {};

  Object.values(descriptions).forEach((section) => {
    if (section && typeof section === 'object' && !Array.isArray(section)) {
      Object.entries(section).forEach(([field, description]) => {
        if (typeof description === 'string' && description.trim().length > 0) {
          result[field] = description;
        }
      });
    }
  });

  return result;
};

const prepareRecordForExport = (
  record: Record<string, BondFieldValue> | null,
  columnMapping: Record<string, string>,
): Record<string, string> => {
  if (!record) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(record).map(([field, value]) => [
      columnMapping[field] ?? field,
      formatFieldValue(field, value),
    ]),
  );
};

/**
 * Export selected bonds to JSON
 * Structure: { "Bond Name": { securities: {...}, marketdata: {...}, marketdata_yields: [...], Купоны: [...] } }
 * Купоны: Array of { "Дата платежа": string, "Сумма купона": string, "Процент купона от номинала": string }
 */
export const exportSelectedBonds = async (secids: string[]): Promise<void> => {
  if (secids.length === 0) {
    throw new Error('Не выбрано ни одной облигации');
  }

  // Load metadata once
  const [columnMapping, descriptionsResponse] = await Promise.all([
    fetchColumnMapping(),
    fetchDescriptions(),
  ]);

  const fieldDescriptions = flattenDescriptions(descriptionsResponse);

  // Load all bond details and coupons
  const bondDetailsPromises = secids.map(secid => fetchBondDetail(secid));
  const bondDetails = await Promise.all(bondDetailsPromises);

  // Load coupons for all bonds in parallel
  const couponsPromises = secids.map(secid => 
    fetchBondCoupons(secid).catch(() => ({ coupons: [] as Coupon[] }))
  );
  const couponsResponses = await Promise.all(couponsPromises);

  // Build export structure
  const exportData: Record<string, Record<string, unknown>> = {};

  for (let i = 0; i < bondDetails.length; i++) {
    const bondDetail = bondDetails[i];
    const secid = secids[i];
    const coupons = couponsResponses[i]?.coupons || [];

    // Get bond name from securities data
    const bondName = 
      (typeof bondDetail.securities?.SHORTNAME === 'string' && bondDetail.securities.SHORTNAME) ||
      (typeof bondDetail.securities?.SECNAME === 'string' && bondDetail.securities.SECNAME) ||
      secid;

    const payload: Record<string, unknown> = {
      securities: prepareRecordForExport(bondDetail.securities, columnMapping),
    };

    if (bondDetail.marketdata) {
      payload.marketdata = prepareRecordForExport(bondDetail.marketdata, columnMapping);
    }

    if (bondDetail.marketdata_yields?.length) {
      payload.marketdata_yields = bondDetail.marketdata_yields.map((entry) =>
        prepareRecordForExport(entry, columnMapping)
      );
    }

    // Add coupons section
    if (coupons.length > 0) {
      payload.Купоны = coupons.map((coupon) => ({
        'Дата платежа': coupon.coupondate ? formatDate(coupon.coupondate) : '—',
        'Сумма купона': coupon.value !== null && coupon.value !== undefined 
          ? formatNumber(coupon.value, 2) 
          : '—',
        'Процент купона от номинала': coupon.valueprc !== null && coupon.valueprc !== undefined
          ? formatPercent(coupon.valueprc)
          : '—',
      }));
    } else {
      payload.Купоны = [];
    }

    exportData[bondName] = payload;
  }

  // Create and download JSON file
  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `bonds_export_${new Date().toISOString().split('T')[0]}.json`;
  link.click();

  URL.revokeObjectURL(url);
};

