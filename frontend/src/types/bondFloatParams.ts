/**
 * TypeScript interface matching backend BondFloatParamsDTO (Pydantic model).
 * All fields from Bond (secid, name_short, maturity_date, nominal, days_to_maturity)
 * plus all BondFloatParams fields for the floater card display.
 */
export interface BondFloatParamsDTO {
  secid: string;
  name_short: string | null;
  maturity_date: string | null;
  nominal: number | null;
  days_to_maturity: number | null;

  is_find: number;
  base_indicator_code: string;
  spread: number | null;
  coupon_frequency_days: number | null;
  lookback_period: number | null;
  averaging_period: number | null;
  formula_raw: string | null;
  rate_determination_rule: string | null;
  calculation_type: string | null;
  rounding_precision: number | null;
  key_rate_method: string | null;
  lookback_type: string | null;
  year_base: string | null;
  is_daily_accrual: boolean;
  offset_days: number | null;
  offset_calendar: string | null;
  day_count: string | null;
  fallback: string | null;
  accrual_type: string | null;
  interest_compounding: boolean;
  placement_date: string | null;
  underwriter: string | null;
  floor_rate: number | null;
  cap_rate: number | null;
  extra_indicators: string | null;
  condition_logic: string | null;
  observation_type: string | null;
  reference_period_desc: string | null;
}
