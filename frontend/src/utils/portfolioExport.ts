import type { PortfolioBond } from '../types/bond';
import { exportSelectedBonds } from './bondExport';
import { fetchBondDetail, fetchBondCoupons } from '../api/bonds';
import { fetchDescriptions, fetchColumnMapping } from '../api/metadata';
import type { DescriptionsResponse } from '../api/metadata';
import type { ColumnMapping } from '../types/api';
import type { BondFieldValue } from '../types/bond';
import { formatDate, formatNumber, formatPercent } from './formatters';

/**
 * Portfolio export format types
 */
export type PortfolioExportFormat = 'full' | 'secid-only' | 'markdown';

/**
 * Portfolio file format for SECID-only export
 */
export interface PortfolioSecidFormat {
  version: string;
  format: 'secid-only';
  secids: string[];
  quantities?: Record<string, number>; // Map of SECID to quantity
  exportedAt: string;
}

/**
 * Export portfolio in full format (same as bonds export)
 * Uses the same exportSelectedBonds function, but also saves quantities separately
 */
export const exportPortfolioFull = async (bonds: PortfolioBond[]): Promise<void> => {
  if (bonds.length === 0) {
    throw new Error('Портфель пуст. Нет облигаций для экспорта.');
  }

  // Remove duplicate SECIDs while preserving order
  const uniqueSecids = Array.from(new Set(bonds.map(bond => bond.SECID)));
  
  // Export bonds data using existing function
  await exportSelectedBonds(uniqueSecids);
  
  // Create a separate file for quantities if any bond has quantity != 1
  const quantities: Record<string, number> = {};
  bonds.forEach(bond => {
    if (bond.quantity && bond.quantity !== 1) {
      quantities[bond.SECID] = bond.quantity;
    }
  });
  
  // If there are non-default quantities, save them in a separate file
  if (Object.keys(quantities).length > 0) {
    const quantitiesData = {
      version: '1.0',
      format: 'quantities',
      quantities,
      exportedAt: new Date().toISOString(),
    };
    
    const json = JSON.stringify(quantitiesData, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `portfolio_quantities_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    URL.revokeObjectURL(url);
  }
};

/**
 * Export portfolio in SECID-only format
 * Creates a simple JSON file with SECID values and quantities
 */
export const exportPortfolioSecidOnly = (bonds: PortfolioBond[]): void => {
  if (bonds.length === 0) {
    throw new Error('Портфель пуст. Нет облигаций для экспорта.');
  }

  // Remove duplicate SECIDs while preserving order
  const secids = Array.from(new Set(bonds.map(bond => bond.SECID)));
  
  // Build quantities map (only include if quantity != 1)
  const quantities: Record<string, number> = {};
  bonds.forEach(bond => {
    if (bond.quantity && bond.quantity !== 1) {
      quantities[bond.SECID] = bond.quantity;
    }
  });
  
  const exportData: PortfolioSecidFormat = {
    version: '1.0',
    format: 'secid-only',
    secids,
    ...(Object.keys(quantities).length > 0 && { quantities }),
    exportedAt: new Date().toISOString(),
  };

  // Create and download JSON file
  const json = JSON.stringify(exportData, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `portfolio_${new Date().toISOString().split('T')[0]}.json`;
  link.click();

  URL.revokeObjectURL(url);
};

/**
 * Flatten descriptions from nested structure
 */
const flattenDescriptions = (descriptions: DescriptionsResponse): Record<string, string> => {
  const result: Record<string, string> = {};

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

/**
 * Format field value for markdown display
 */
const formatFieldValueForMarkdown = (
  field: string,
  value: BondFieldValue,
  columnMapping: ColumnMapping,
  fieldDescriptions: Record<string, string>
): string => {
  if (value === null || value === undefined) {
    return '—';
  }

  if (Array.isArray(value)) {
    const formatted = value
      .map((v) => formatFieldValueForMarkdown(field, v as BondFieldValue, columnMapping, fieldDescriptions))
      .filter((v) => v !== '—');
    return formatted.length > 0 ? formatted.join(', ') : '—';
  }

  if (typeof value === 'boolean') {
    return value ? 'Да' : 'Нет';
  }

  const fieldUpper = field.toUpperCase();
  
  if (typeof value === 'number') {
    if (fieldUpper.includes('PERCENT') || fieldUpper.includes('YIELD') || fieldUpper.includes('RATE') || fieldUpper.includes('SPREAD')) {
      return formatPercent(value);
    }
    if (fieldUpper.includes('VALUE') || fieldUpper.includes('PRICE') || fieldUpper.includes('AMOUNT') || fieldUpper.includes('SUM') || fieldUpper.includes('CAPITAL') || fieldUpper.includes('COST')) {
      return formatNumber(value, 2);
    }
    if (fieldUpper.includes('SIZE') || fieldUpper.includes('VOLUME') || fieldUpper.includes('COUNT') || fieldUpper.includes('LOT') || fieldUpper.includes('NUM') || fieldUpper.includes('NUMBER') || fieldUpper.includes('PERIOD') || fieldUpper.includes('QUANTITY')) {
      return formatNumber(value, 0);
    }
    return formatNumber(value, Math.abs(value) < 1 ? 4 : 2);
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.length === 0 || trimmed.toLowerCase() === 'nan') {
      return '—';
    }

    // Check if it's a date
    const isoDateRegex = /^\d{4}-\d{2}-\d{2}/;
    const isoDateTimeRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:/;
    if (fieldUpper.includes('DATE') || isoDateRegex.test(trimmed) || isoDateTimeRegex.test(trimmed)) {
      return formatDate(trimmed);
    }

    // Check if it's a numeric string
    const numericPattern = /^-?\d+(?:[.,]\d+)?$/;
    if (numericPattern.test(trimmed)) {
      const parsed = Number(trimmed.replace(',', '.'));
      return formatFieldValueForMarkdown(field, parsed, columnMapping, fieldDescriptions);
    }

    return trimmed;
  }

  return String(value);
};

/**
 * Get field label from column mapping
 */
const getFieldLabel = (field: string, columnMapping: ColumnMapping): string => {
  return columnMapping[field] || field;
};

/**
 * Get field description
 */
const getFieldDescription = (field: string, fieldDescriptions: Record<string, string>): string | undefined => {
  const direct = fieldDescriptions[field];
  if (direct) {
    return direct;
  }

  if (field.endsWith('BP')) {
    const trimmed = field.slice(0, -2);
    return fieldDescriptions[trimmed];
  }

  return undefined;
};

/**
 * Export portfolio to markdown format with detailed parameter descriptions
 */
export const exportPortfolioToMarkdown = async (bonds: PortfolioBond[]): Promise<void> => {
  if (bonds.length === 0) {
    throw new Error('Портфель пуст. Нет облигаций для экспорта.');
  }

  // Load metadata once
  const [descriptionsResponse, columnMapping] = await Promise.all([
    fetchDescriptions(),
    fetchColumnMapping(),
  ]);

  const fieldDescriptions = flattenDescriptions(descriptionsResponse);

  // Build markdown content
  let markdown = `# Портфель облигаций\n\n`;
  markdown += `**Дата экспорта:** ${formatDate(new Date().toISOString())}\n`;
  markdown += `**Количество облигаций:** ${bonds.length}\n\n`;
  markdown += `---\n\n`;

  // Process each bond
  for (let i = 0; i < bonds.length; i++) {
    const bond = bonds[i];
    
    try {
      // Fetch detailed bond information
      const bondDetail = await fetchBondDetail(bond.SECID);
      
      markdown += `## ${i + 1}. ${bond.SHORTNAME || bond.SECID}\n\n`;
      
      if (bond.quantity && bond.quantity > 1) {
        markdown += `**Количество в портфеле:** ${bond.quantity} шт.\n\n`;
      }

      // Basic information section
      markdown += `### Основная информация\n\n`;
      const securities = bondDetail.securities;
      if (securities) {
        const basicFields = [
          'SECNAME', 'SHORTNAME', 'ISIN', 'REGNUMBER', 'SECTYPE', 'BONDTYPE43',
          'FACEVALUE', 'FACEUNIT', 'CURRENCYID', 'STATUS', 'MATDATE'
        ];
        
        markdown += `| Параметр | Значение | Описание |\n`;
        markdown += `|----------|----------|----------|\n`;
        
        for (const field of basicFields) {
          const value = securities[field];
          if (value !== null && value !== undefined && value !== '') {
            const label = getFieldLabel(field, columnMapping);
            const formattedValue = formatFieldValueForMarkdown(field, value, columnMapping, fieldDescriptions);
            const description = getFieldDescription(field, fieldDescriptions) || '—';
            markdown += `| ${label} | ${formattedValue} | ${description} |\n`;
          }
        }
        markdown += `\n`;
      }

      // Coupon information
      markdown += `### Купонная информация\n\n`;
      if (securities) {
        const couponFields = [
          'COUPONPERCENT', 'COUPONPERIOD', 'COUPONVALUE', 'ACCRUEDINT',
          'NEXTCOUPON', 'COUPONTYPE'
        ];
        
        markdown += `| Параметр | Значение | Описание |\n`;
        markdown += `|----------|----------|----------|\n`;
        
        for (const field of couponFields) {
          const value = securities[field];
          if (value !== null && value !== undefined && value !== '') {
            const label = getFieldLabel(field, columnMapping);
            const formattedValue = formatFieldValueForMarkdown(field, value, columnMapping, fieldDescriptions);
            const description = getFieldDescription(field, fieldDescriptions) || '—';
            markdown += `| ${label} | ${formattedValue} | ${description} |\n`;
          }
        }
        markdown += `\n`;
      }

      // Coupon payments schedule
      try {
        const couponsResponse = await fetchBondCoupons(bond.SECID);
        const coupons = couponsResponse.coupons || [];
        
        if (coupons.length > 0) {
          markdown += `### График купонных выплат\n\n`;
          
          // Get currency from first coupon or securities
          const displayCurrency = coupons[0]?.faceunit || securities?.FACEUNIT || '';
          const couponAmountHeader = displayCurrency 
            ? `Сумма купона, ${displayCurrency}`
            : 'Сумма купона';
          
          markdown += `| Дата купона | ${couponAmountHeader} | Ставка купона | Номинал на дату выплаты | Дата начала периода | Дата фиксации |\n`;
          markdown += `|-------------|${'-'.repeat(Math.max(25, couponAmountHeader.length))}|---------------|-------------------------|---------------------|---------------|\n`;
          
          for (const coupon of coupons) {
            const couponDate = coupon.coupondate ? formatDate(coupon.coupondate) : '—';
            const couponValue = coupon.value !== null && coupon.value !== undefined 
              ? formatNumber(coupon.value, 2) 
              : '—';
            const couponRate = coupon.valueprc !== null && coupon.valueprc !== undefined 
              ? formatPercent(coupon.valueprc) 
              : '—';
            const faceValue = coupon.facevalue !== null && coupon.facevalue !== undefined 
              ? formatNumber(coupon.facevalue, 2) 
              : '—';
            const startDate = coupon.startdate ? formatDate(coupon.startdate) : '—';
            const recordDate = coupon.recorddate ? formatDate(coupon.recorddate) : '—';
            
            markdown += `| ${couponDate} | ${couponValue} | ${couponRate} | ${faceValue} | ${startDate} | ${recordDate} |\n`;
          }
          markdown += `\n`;
        }
      } catch (couponError) {
        console.warn(`Failed to fetch coupons for bond ${bond.SECID}:`, couponError);
        // Don't fail the entire export if coupons can't be loaded
      }

      // Market data
      if (bondDetail.marketdata) {
        markdown += `### Рыночные данные\n\n`;
        const market = bondDetail.marketdata;
        const marketFields = [
          'PREVPRICE', 'LAST', 'WAPRICE', 'BID', 'OFFER', 'SPREAD',
          'YIELDATPREVWAPRICE', 'VOLTODAY', 'VALTODAY', 'NUMTRADES'
        ];
        
        markdown += `| Параметр | Значение | Описание |\n`;
        markdown += `|----------|----------|----------|\n`;
        
        for (const field of marketFields) {
          const value = market[field];
          if (value !== null && value !== undefined && value !== '') {
            const label = getFieldLabel(field, columnMapping);
            const formattedValue = formatFieldValueForMarkdown(field, value, columnMapping, fieldDescriptions);
            const description = getFieldDescription(field, fieldDescriptions) || '—';
            markdown += `| ${label} | ${formattedValue} | ${description} |\n`;
          }
        }
        markdown += `\n`;
      }

      // Yield data
      if (bondDetail.marketdata_yields && bondDetail.marketdata_yields.length > 0) {
        markdown += `### Доходность и расчёты\n\n`;
        const yields = bondDetail.marketdata_yields[0];
        const yieldFields = [
          'YIELD', 'EFFECTIVEYIELD', 'YIELDTOOFFER', 'CALLOPTIONYIELD',
          'GSPREADBP', 'ZSPREADBP', 'DURATION', 'DURATIONWAPRICE'
        ];
        
        markdown += `| Параметр | Значение | Описание |\n`;
        markdown += `|----------|----------|----------|\n`;
        
        for (const field of yieldFields) {
          const value = yields[field];
          if (value !== null && value !== undefined && value !== '') {
            const label = getFieldLabel(field, columnMapping);
            const formattedValue = formatFieldValueForMarkdown(field, value, columnMapping, fieldDescriptions);
            const description = getFieldDescription(field, fieldDescriptions) || '—';
            markdown += `| ${label} | ${formattedValue} | ${description} |\n`;
          }
        }
        markdown += `\n`;
      }

      // Additional fields section
      markdown += `### Дополнительные параметры\n\n`;
      if (securities) {
        const allFields = Object.keys(securities).filter(field => {
          const excludedFields = new Set([
            'SECID', 'SECNAME', 'SHORTNAME', 'ISIN', 'REGNUMBER', 'SECTYPE', 'BONDTYPE43',
            'FACEVALUE', 'FACEUNIT', 'CURRENCYID', 'STATUS', 'MATDATE',
            'COUPONPERCENT', 'COUPONPERIOD', 'COUPONVALUE', 'ACCRUEDINT', 'NEXTCOUPON', 'COUPONTYPE',
            'IR', 'ICPI', 'BEI', 'BEICLOSE', 'CBR', 'CBRCLOSE', 'IRICPICLOSE',
            'SYSTIME', 'UPDATETIME', 'TIME', 'TRADEMOMENT',
            'BIDDEPTH', 'OFFERDEPTH',
          ]);
          return !excludedFields.has(field);
        });

        if (allFields.length > 0) {
          markdown += `| Параметр | Значение | Описание |\n`;
          markdown += `|----------|----------|----------|\n`;
          
          for (const field of allFields) {
            const value = securities[field];
            if (value !== null && value !== undefined && value !== '') {
              const label = getFieldLabel(field, columnMapping);
              const formattedValue = formatFieldValueForMarkdown(field, value, columnMapping, fieldDescriptions);
              const description = getFieldDescription(field, fieldDescriptions) || '—';
              markdown += `| ${label} | ${formattedValue} | ${description} |\n`;
            }
          }
          markdown += `\n`;
        }
      }

      markdown += `---\n\n`;
    } catch (error) {
      console.error(`Failed to fetch details for bond ${bond.SECID}:`, error);
      markdown += `**Ошибка:** Не удалось загрузить детальную информацию об облигации ${bond.SECID}\n\n`;
      markdown += `---\n\n`;
    }
  }

  // Create and download markdown file
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `portfolio_detailed_${new Date().toISOString().split('T')[0]}.md`;
  link.click();

  URL.revokeObjectURL(url);
};

/**
 * Export portfolio based on selected format
 */
export const exportPortfolio = async (
  bonds: PortfolioBond[],
  format: PortfolioExportFormat
): Promise<void> => {
  if (format === 'full') {
    await exportPortfolioFull(bonds);
  } else if (format === 'markdown') {
    await exportPortfolioToMarkdown(bonds);
  } else {
    exportPortfolioSecidOnly(bonds);
  }
};
