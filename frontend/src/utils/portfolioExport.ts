import type { BondListItem } from '../types/bond';
import { exportSelectedBonds } from './bondExport';

/**
 * Portfolio export format types
 */
export type PortfolioExportFormat = 'full' | 'secid-only';

/**
 * Portfolio file format for SECID-only export
 */
export interface PortfolioSecidFormat {
  version: string;
  format: 'secid-only';
  secids: string[];
  exportedAt: string;
}

/**
 * Export portfolio in full format (same as bonds export)
 * Uses the same exportSelectedBonds function
 */
export const exportPortfolioFull = async (bonds: BondListItem[]): Promise<void> => {
  if (bonds.length === 0) {
    throw new Error('Портфель пуст. Нет облигаций для экспорта.');
  }

  const secids = bonds.map(bond => bond.SECID);
  await exportSelectedBonds(secids);
};

/**
 * Export portfolio in SECID-only format
 * Creates a simple JSON file with only SECID values
 */
export const exportPortfolioSecidOnly = (bonds: BondListItem[]): void => {
  if (bonds.length === 0) {
    throw new Error('Портфель пуст. Нет облигаций для экспорта.');
  }

  const secids = bonds.map(bond => bond.SECID);
  
  const exportData: PortfolioSecidFormat = {
    version: '1.0',
    format: 'secid-only',
    secids,
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
 * Export portfolio based on selected format
 */
export const exportPortfolio = async (
  bonds: BondListItem[],
  format: PortfolioExportFormat
): Promise<void> => {
  if (format === 'full') {
    await exportPortfolioFull(bonds);
  } else {
    exportPortfolioSecidOnly(bonds);
  }
};
