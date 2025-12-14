import type { PortfolioBond } from '../types/bond';
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

  const secids = bonds.map(bond => bond.SECID);
  
  // Export bonds data using existing function
  await exportSelectedBonds(secids);
  
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

  const secids = bonds.map(bond => bond.SECID);
  
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
 * Export portfolio based on selected format
 */
export const exportPortfolio = async (
  bonds: PortfolioBond[],
  format: PortfolioExportFormat
): Promise<void> => {
  if (format === 'full') {
    await exportPortfolioFull(bonds);
  } else {
    exportPortfolioSecidOnly(bonds);
  }
};
