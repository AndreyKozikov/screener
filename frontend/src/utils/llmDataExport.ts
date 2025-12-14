import { fetchBondDetail, fetchBondCoupons } from '../api/bonds';
import { fetchColumnMapping, fetchDescriptions } from '../api/metadata';
import { fetchZerocuponData } from '../api/zerocupon';
import { fetchForecastData } from '../api/forecast';
import type { BondFieldValue } from '../types/bond';
import type { Coupon } from '../types/coupon';
import { formatDate, formatNumber, formatPercent } from './formatters';

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

// const flattenDescriptions = (descriptions: any): FieldDescriptionMap => {
//   const result: FieldDescriptionMap = {};
//
//   Object.values(descriptions).forEach((section) => {
//     if (section && typeof section === 'object' && !Array.isArray(section)) {
//       Object.entries(section).forEach(([field, description]) => {
//         if (typeof description === 'string' && description.trim().length > 0) {
//           result[field] = description;
//         }
//       });
//     }
//   });
//
//   return result;
// };

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
 * Get bonds data for LLM analysis (returns JSON string, doesn't download)
 */
export const getBondsDataForLLM = async (secids: string[]): Promise<string> => {
  if (secids.length === 0) {
    throw new Error('Не выбрано ни одной облигации');
  }

  console.log(`[LLM Export] Loading bonds data for ${secids.length} bonds...`);

  // Step 1: Load metadata first
  const [columnMapping] = await Promise.all([
    fetchColumnMapping(),
    fetchDescriptions(),
  ]);

  // const fieldDescriptions = flattenDescriptions(descriptionsResponse);

  // Step 2: Load all bond details and coupons (all data loaded before processing)
  console.log(`[LLM Export] Loading bond details for ${secids.length} bonds...`);
  const bondDetailsPromises = secids.map(secid => fetchBondDetail(secid));
  const bondDetails = await Promise.all(bondDetailsPromises);
  console.log(`[LLM Export] Bond details loaded: ${bondDetails.length}`);

  // Step 3: Load coupons for all bonds in parallel (all data loaded before processing)
  console.log(`[LLM Export] Loading coupons for ${secids.length} bonds...`);
  const couponsPromises = secids.map(secid => 
    fetchBondCoupons(secid).catch(() => ({ coupons: [] as Coupon[] }))
  );
  const couponsResponses = await Promise.all(couponsPromises);
  console.log(`[LLM Export] Coupons loaded: ${couponsResponses.length}`);

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

  // Step 4: Convert to JSON string (all data is already loaded)
  const jsonString = JSON.stringify(exportData, null, 2);
  console.log(`[LLM Export] Bonds data prepared: ${jsonString.length} characters`);
  return jsonString;
};

/**
 * Get zero-coupon yield curve data for LLM analysis (returns JSON string, doesn't download)
 */
export const getZerocuponDataForLLM = async (
  dateFrom: string,
  dateTo: string
): Promise<string> => {
  console.log(`[LLM Export] Loading zerocupon data from ${dateFrom} to ${dateTo}...`);
  const response = await fetchZerocuponData(dateFrom, dateTo);
  console.log(`[LLM Export] Zerocupon data loaded: ${response.data.length} records`);
  
  // Build LLM-friendly JSON structure (same as download endpoint)
  const periodColumns = Object.keys(response.data[0] || {}).filter(
    (key) => key !== 'Дата' && key !== 'Время'
  );

  const extractPeriodYears = (colName: string): number | null => {
    const match = colName.match(/(\d+\.?\d*)/);
    if (match) {
      try {
        return parseFloat(match[1]);
      } catch {
        return null;
      }
    }
    return null;
  };

  const dataRecords = response.data.map((row) => {
    const record: any = {
      date: row.Дата,
      time: row.Время || null,
      yield_curve: {},
    };

    for (const col of periodColumns) {
      const periodYears = extractPeriodYears(col);
      if (periodYears !== null) {
        const value = row[col];
        if (value !== null && value !== undefined && value !== '') {
          const numValue = typeof value === 'string' 
            ? parseFloat(value.replace(',', '.')) 
            : value;
          if (!isNaN(numValue as number)) {
            record.yield_curve[String(periodYears)] = numValue;
          }
        }
      }
    }

    return record;
  });

  const periodsList: number[] = [];
  for (const col of periodColumns) {
    const period = extractPeriodYears(col);
    if (period !== null) {
      periodsList.push(period);
    }
  }

  const exportData = {
    metadata: {
      title: 'Кривая бескупонной доходности',
      description: 'Данные кривой бескупонной доходности (БКДЦТ) с различными сроками до погашения',
      date_from: dateFrom,
      date_to: dateTo,
      record_count: dataRecords.length,
      export_date: new Date().toISOString(),
      periods: periodsList.sort((a, b) => a - b),
    },
    field_descriptions: {
      date: 'Дата расчета кривой доходности в формате DD.MM.YYYY',
      time: 'Время расчета (если доступно)',
      yield_curve: 'Словарь значений доходности по срокам до погашения (в годах). Ключи - сроки в годах, значения - доходность в процентах годовых',
    },
    data: dataRecords,
  };

  const jsonString = JSON.stringify(exportData, null, 2);
  console.log(`[LLM Export] Zerocupon data prepared: ${jsonString.length} characters`);
  return jsonString;
};

/**
 * Get forecast data for LLM analysis (returns JSON string, doesn't download)
 */
export const getForecastDataForLLM = async (date: string): Promise<string> => {
  console.log(`[LLM Export] Loading forecast data for date ${date}...`);
  const forecastData = await fetchForecastData(date);
  console.log(`[LLM Export] Forecast data loaded`);
  
  // Build export structure (same as download endpoint)
  const exportData: Record<string, any> = {};
  
  const names = forecastData.names;
  const mainNames = names.основные_показатели;
  const balanceNames = names.платёжный_баланс;
  
  const dateData = forecastData.data;
  const dateExport: any = {
    дата_заседания: dateData.дата_заседания,
    дата_публикации: dateData.дата_публикации,
    основные_показатели: {},
    платёжный_баланс: {},
  };

  // Process main indicators
  const mainIndicators = dateData.основные_показатели;
  if (mainIndicators) {
    const years = [...new Set(mainIndicators.map((ind: any) => ind.год))].sort();
    for (const year of years) {
      const yearData = mainIndicators.find((ind: any) => ind.год === year);
      if (yearData) {
        const yearDict: Record<string, any> = {};
        for (const [key, value] of Object.entries(yearData)) {
          if (key === 'год') continue;
          if (key in mainNames) {
            yearDict[mainNames[key]] = value;
          }
        }
        if (Object.keys(yearDict).length > 0) {
          dateExport.основные_показатели[String(year)] = yearDict;
        }
      }
    }
  }

  // Process balance indicators
  const balanceIndicators = dateData.платёжный_баланс;
  if (balanceIndicators) {
    const years = [...new Set(balanceIndicators.map((ind: any) => ind.год))].sort();
    for (const year of years) {
      const yearData = balanceIndicators.find((ind: any) => ind.год === year);
      if (yearData) {
        const yearDict: Record<string, any> = {};
        for (const [key, value] of Object.entries(yearData)) {
          if (key === 'год') continue;
          if (key in balanceNames) {
            yearDict[balanceNames[key]] = value;
          }
        }
        if (Object.keys(yearDict).length > 0) {
          dateExport.платёжный_баланс[String(year)] = yearDict;
        }
      }
    }
  }

  exportData[date] = dateExport;

  const jsonString = JSON.stringify(exportData, null, 2);
  console.log(`[LLM Export] Forecast data prepared: ${jsonString.length} characters`);
  return jsonString;
};

