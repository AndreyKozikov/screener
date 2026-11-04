import { apiClient } from './client';
import type { PortfolioBond } from '../types/bond';

export interface PortfolioPositionValuation {
  bond_id: number | null;
  secid: string;
  isin: string | null;
  name: string | null;
  quantity: number;
  nominal: string;
  clean_price: string;
  accrued_interest: string;
  accrued_interest_percent: string;
  dirty_price: string;
  market_value: string;
  weight: string;
  weight_percent: string;
  ytm: string | null;
  ytm_percent: string | null;
  average_purchase_price: string | null;
  maturity_date: string | null;
  coupon_period_start: string | null;
  coupon_period_end: string | null;
  accrued_days: number;
  period_days: number;
  day_count_convention: string;
  currency: string | null;
}

export interface PortfolioValuation {
  portfolio_id: number | null;
  portfolio_name: string | null;
  valuation_date: string;
  currency: string | null;
  total_market_value: string;
  total_nominal_value: string;
  weighted_ytm: string | null;
  weighted_ytm_percent: string | null;
  true_ytm: string | null;
  true_ytm_percent: string | null;
  positions: PortfolioPositionValuation[];
  warnings: string[];
}

export const fetchPortfolioValuation = async (
  bonds: PortfolioBond[],
  valuationDate: string,
): Promise<PortfolioValuation> => {
  const response = await apiClient.post<PortfolioValuation>('/portfolio/valuation', {
    valuation_date: valuationDate,
    positions: bonds.map((bond) => ({
      secid: bond.SECID,
      isin: bond.ISIN,
      quantity: bond.quantity,
      average_purchase_price: bond.averagePurchasePrice,
    })),
  });
  return response.data;
};
