import { apiClient } from './client';
import type { PortfolioBond } from '../types/bond';

export interface PortfolioReportImportResponse {
  portfolio_id: number;
  portfolio_name: string;
  report_period_start: string | null;
  report_period_end: string | null;
  import_status: string;
  trade_count: number;
  security_count: number;
  cash_operation_count: number;
  income_payment_count: number;
  position_count: number;
  security_movement_count: number;
  parse_error_count: number;
  duplicate: boolean;
  warnings: string[];
}

export interface ImportedPortfolioSummary {
  portfolio_id: number;
  portfolio_name: string;
  base_currency: string;
  source_file_name: string;
  report_period_start: string | null;
  report_period_end: string | null;
  created_at: string;
  import_status: string;
  records_summary: Record<string, number>;
}

export async function importPortfolioReport(
  file: File,
  portfolioName: string,
): Promise<PortfolioReportImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('portfolio_name', portfolioName);
  const response = await apiClient.post<PortfolioReportImportResponse>('/portfolios/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function fetchImportedPortfolios(): Promise<ImportedPortfolioSummary[]> {
  const response = await apiClient.get<ImportedPortfolioSummary[]>('/portfolios');
  return response.data;
}

export async function deleteImportedPortfolio(portfolioId: number): Promise<void> {
  await apiClient.delete(`/portfolios/${portfolioId}`);
}

export async function fetchImportedPortfolioTable(portfolioId: number): Promise<PortfolioBond[]> {
  const response = await apiClient.get<PortfolioBond[]>(`/portfolios/${portfolioId}/table`);
  return response.data;
}
