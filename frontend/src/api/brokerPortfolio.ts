import type { PortfolioBond } from '../types/bond';
import { apiClient } from './client';

export interface BrokerPortfolioPosition {
  isin: string;
  quantity: number;
  averagePurchasePrice: number;
}

export interface BrokerPortfolioImportResponse {
  imported_count: number;
  positions: BrokerPortfolioPosition[];
  warnings: string[];
}

export const importBrokerReport = async (file: File): Promise<BrokerPortfolioImportResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<BrokerPortfolioImportResponse>(
    '/portfolio/import/broker-report',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );

  return response.data;
};

export type BrokerPortfolioImportMode = 'merge' | 'replace';
export type BrokerPortfolioImportHandler = (
  bonds: PortfolioBond[],
  mode: BrokerPortfolioImportMode,
) => void;
