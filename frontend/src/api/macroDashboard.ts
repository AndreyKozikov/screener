import { apiClient } from './client';

export interface MacroDashboardIndicator {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  date: string | null;
  change: number | null;
  change_unit: string;
  change_label: string;
  tone: 'нейтральный' | 'дезинфляционный' | 'инфляционный';
}

export interface MacroSignalMetric {
  key: string;
  label: string;
  value: number | null;
  date: string | null;
  change: number | null;
  change_90d: number | null;
  unit: string;
  threshold: number;
  weight: number;
  signal: number | null;
}

export interface MacroSignal {
  key: string;
  name: string;
  score: number | null;
  status: string;
  trend: 'up' | 'down' | 'stable' | 'mixed' | 'unknown';
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  signal_count: number;
  data_coverage: number;
  available_weight: number;
  configured_weight: number;
  is_available: boolean;
  explanation: string;
  indicators: MacroSignalMetric[];
}

export interface MacroBalanceGroup {
  key: 'cut' | 'hold' | 'hike';
  label: string;
  count: number;
  weight: number;
  share: number;
}

export interface MacroAssessment {
  index: number | null;
  raw_index?: number;
  status: string;
  coverage: number;
  classified_weight: number;
  interpretation: string;
  balance: MacroBalanceGroup[];
  is_available: boolean;
  note: string;
}

export interface MacroDashboardResponse {
  generated_at: string;
  dashboard_indicators: MacroDashboardIndicator[];
  dashboard_charts: {
    inflation: Array<{ date: string; mom: number | null; yoy: number | null }>;
    expectations: Array<{ date: string; actual_yoy: number | null; expected_1y: number | null; expected_5y: number | null }>;
    expectation_gaps: {
      one_year: { value: number | null; date: string | null };
      five_year: { value: number | null; date: string | null };
    };
    monetary_conditions: Array<{ date: string; key_rate: number | null; ruonia: number | null }>;
    yield_curve: {
      date: string | null;
      comparison_date: string | null;
      data: Array<{ term: string; maturity: string; years: number; current: number | null; previous: number | null; change: number | null }>;
      history: Array<{
        date: string;
        data: Array<{ term: string; maturity: string; years: number; value: number | null }>;
      }>;
    };
  };
  macro_signals: MacroSignal[];
  macro_assessment: MacroAssessment;
  indicator_calculations: Record<string, {
    value: number | null;
    date: string | null;
    change: number | null;
    change_3m: number | null;
    change_6m: number | null;
    mean_recent: number | null;
    mean_previous: number | null;
    trend_delta: number | null;
    status: string;
  }>;
  data_quality: {
    source_counts: Record<string, number>;
    source_errors: Record<string, string>;
    warnings: string[];
  };
}

export const fetchMacroDashboard = async (): Promise<MacroDashboardResponse> => {
  const response = await apiClient.get<MacroDashboardResponse>('/macro-dashboard');
  return response.data;
};
