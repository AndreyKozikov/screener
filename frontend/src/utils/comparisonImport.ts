import type { BondListItem } from '../types/bond';
import { fetchBonds } from '../api/bonds';
import type { BondsListResponse } from '../types/api';
import type { PortfolioSecidFormat } from './portfolioExport';

/**
 * Comparison import result
 */
export interface ComparisonImportResult {
  secids: string[];
  bonds: BondListItem[];
  errors: string[];
}

/**
 * Check if file content is in SECID-only format
 */
const isSecidOnlyFormat = (data: unknown): data is PortfolioSecidFormat => {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const obj = data as Record<string, unknown>;
  
  // Check for new format with version and format fields
  if (obj.format === 'secid-only' && Array.isArray(obj.secids)) {
    return obj.secids.every((secid: unknown) => typeof secid === 'string' && secid.length > 0);
  }

  // Check for simple array format (backward compatibility)
  if (Array.isArray(data)) {
    return data.every((item: unknown) => typeof item === 'string' && item.length > 0);
  }

  return false;
};

/**
 * Check if file content is in full export format (from exportSelectedBonds)
 * Format: { "Bond Name": { securities: {...}, marketdata: {...}, ... } }
 */
const isFullExportFormat = (data: unknown): boolean => {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return false;
  }

  const obj = data as Record<string, unknown>;
  
  // Check if it's an object with bond names as keys
  // Each value should have securities, marketdata, etc.
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const bondData = obj[key];
      if (bondData && typeof bondData === 'object' && !Array.isArray(bondData)) {
        const bondObj = bondData as Record<string, unknown>;
        // Check if it has securities field (indicating full export format)
        if (bondObj.securities && typeof bondObj.securities === 'object') {
          const securities = bondObj.securities as Record<string, unknown>;
          // Check if securities has SECID
          if (typeof securities.SECID === 'string') {
            return true;
          }
        }
      }
    }
  }

  return false;
};

/**
 * Extract SECIDs from full export format
 * Handles both original field name (SECID) and mapped field name (Код инструмента)
 */
const extractSecidsFromFullFormat = (data: Record<string, unknown>): string[] => {
  const secids: string[] = [];

  for (const key in data) {
    if (Object.prototype.hasOwnProperty.call(data, key)) {
      const bondData = data[key];
      if (bondData && typeof bondData === 'object' && !Array.isArray(bondData)) {
        const bondObj = bondData as Record<string, unknown>;
        if (bondObj.securities && typeof bondObj.securities === 'object') {
          const securities = bondObj.securities as Record<string, unknown>;
          
          // Try original field name first
          if (typeof securities.SECID === 'string' && securities.SECID.length > 0) {
            secids.push(securities.SECID);
            continue;
          }
          
          // Try mapped field name (Код инструмента)
          if (typeof securities['Код инструмента'] === 'string' && 
              (securities['Код инструмента'] as string).length > 0) {
            secids.push(securities['Код инструмента'] as string);
            continue;
          }
        }
      }
    }
  }

  return secids;
};

/**
 * Extract SECIDs from SECID-only format
 */
const extractSecidsFromSecidFormat = (
  data: PortfolioSecidFormat | string[]
): string[] => {
  if (Array.isArray(data)) {
    return data.filter((secid: unknown) => typeof secid === 'string' && secid.length > 0);
  }

  if (data.format === 'secid-only' && Array.isArray(data.secids)) {
    return data.secids.filter((secid: unknown) => typeof secid === 'string' && secid.length > 0);
  }

  return [];
};

/**
 * Parse comparison file and extract SECIDs
 */
export const parseComparisonFile = (fileContent: string): string[] => {
  let parsedData: unknown;

  try {
    parsedData = JSON.parse(fileContent);
  } catch (error) {
    throw new Error('Неверный формат JSON файла. Убедитесь, что файл содержит корректный JSON.');
  }

  // Try SECID-only format first (simpler)
  if (isSecidOnlyFormat(parsedData)) {
    return extractSecidsFromSecidFormat(parsedData as PortfolioSecidFormat | string[]);
  }

  // Try full export format
  if (isFullExportFormat(parsedData)) {
    return extractSecidsFromFullFormat(parsedData as Record<string, unknown>);
  }

  // If neither format matches, try to extract SECIDs from any structure
  // This is a fallback for edge cases
  if (typeof parsedData === 'object' && parsedData !== null) {
    const obj = parsedData as Record<string, unknown>;
    
    // Check if it's an object with a secids array
    if (Array.isArray(obj.secids)) {
      return extractSecidsFromSecidFormat(obj.secids);
    }

    // Check if it's an object with securities array
    if (Array.isArray(obj.securities)) {
      const secids: string[] = [];
      for (const item of obj.securities) {
        if (item && typeof item === 'object' && !Array.isArray(item)) {
          const securities = item as Record<string, unknown>;
          if (typeof securities.SECID === 'string') {
            secids.push(securities.SECID);
          }
        }
      }
      if (secids.length > 0) {
        return secids;
      }
    }
  }

  throw new Error(
    'Неверный формат файла. ' +
    'Файл должен быть в формате экспорта портфеля (полные данные или только SECID).'
  );
};

/**
 * Load bonds data by SECIDs from API and convert to BondListItem
 */
const loadBondsBySecids = async (secids: string[]): Promise<BondListItem[]> => {
  if (secids.length === 0) {
    return [];
  }

  // Fetch all bonds (no filters) to get the full list
  // Then filter by SECIDs on client side
  const response: BondsListResponse = await fetchBonds({
    couponMin: null,
    couponMax: null,
    yieldMin: null,
    yieldMax: null,
    couponYieldMin: null,
    couponYieldMax: null,
    matdateFrom: null,
    matdateTo: null,
    listlevel: [],
    faceunit: [],
    bondtype: [],
    bondtype43: [],
    couponType: [],
    ratingMin: null,
    ratingMax: null,
    search: '',
    skip: 0,
    limit: 10000, // Large limit to get all bonds
  });

  // Filter bonds by SECIDs
  const secidSet = new Set(secids);
  const bonds: BondListItem[] = response.bonds.filter(bond => secidSet.has(bond.SECID));

  return bonds;
};

/**
 * Import comparison bonds from file
 * Returns SECIDs and loaded bonds, with any errors encountered
 */
export const importComparisonFromFile = async (file: File): Promise<ComparisonImportResult> => {
  const errors: string[] = [];

  // Read file content
  let fileContent: string;
  try {
    fileContent = await file.text();
  } catch (error) {
    throw new Error('Не удалось прочитать файл. Убедитесь, что файл не поврежден.');
  }

  // Parse file and extract SECIDs
  let secids: string[];
  try {
    secids = parseComparisonFile(fileContent);
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('Не удалось обработать файл.');
  }

  if (secids.length === 0) {
    throw new Error('В файле не найдено ни одного SECID облигации.');
  }

  // Remove duplicates
  const uniqueSecids = Array.from(new Set(secids));

  // Load bonds data from API
  let bonds: BondListItem[] = [];
  try {
    bonds = await loadBondsBySecids(uniqueSecids);
    
    // Check if some bonds were not found
    const foundSecids = new Set(bonds.map(b => b.SECID));
    const notFoundSecids = uniqueSecids.filter(secid => !foundSecids.has(secid));
    
    if (notFoundSecids.length > 0) {
      errors.push(
        `Не найдено облигаций с SECID: ${notFoundSecids.slice(0, 10).join(', ')}` +
        (notFoundSecids.length > 10 ? ` и еще ${notFoundSecids.length - 10}` : '')
      );
    }
  } catch (error) {
    errors.push(
      error instanceof Error 
        ? `Ошибка при загрузке данных облигаций: ${error.message}`
        : 'Ошибка при загрузке данных облигаций'
    );
  }

  return {
    secids: uniqueSecids,
    bonds,
    errors,
  };
};

