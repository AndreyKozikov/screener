import { apiClient } from './client';

export interface PortfolioDeal {
  id: number;
  portfolio_id: number;
  security_id: number | null;
  trade_date: string;
  settlement_date: string | null;
  trade_time: string | null;
  operation_type: 'BUY' | 'SELL' | string;
  quantity: number;
  price_percent_scaled: number | null;
  amount_ex_nkd_minor: number | null;
  nkd_minor: number | null;
  broker_fee_minor: number | null;
  exchange_fee_minor: number | null;
  currency_code: string | null;
  trade_number: string | null;
  status: string | null;
  comment: string | null;
  source_row_number: number | null;
  raw_data_json: string | null;
  isin: string | null;
  security_code: string | null;
  security_name: string | null;
  security_currency_code: string | null;
  asset_type: string | null;
  security_category: string | null;
  issuer: string | null;
  security_raw_data_json: string | null;
  current_quantity: number | null;
}

export interface PortfolioDealsResponse {
  portfolio_id: number;
  portfolio_name: string;
  base_currency: string;
  deals: PortfolioDeal[];
}

export async function fetchPortfolioDeals(portfolioId: number): Promise<PortfolioDealsResponse> {
  const response = await apiClient.get<PortfolioDealsResponse>(`/portfolios/${portfolioId}/deals`);
  return response.data;
}
