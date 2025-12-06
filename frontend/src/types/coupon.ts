/**
 * Coupon data interfaces matching backend Pydantic models
 */

export interface Coupon {
  // Removed duplicate fields: isin, name, issuevalue, primary_boardid, secid, coupon_type
  // These are now only in amortizations section
  coupondate: string | null;
  recorddate: string | null;
  startdate: string | null;
  initialfacevalue: number | null;
  facevalue: number | null;
  faceunit: string | null;
  value: number | null;  // Сумма купона
  valueprc: number | null;  // Ставка купона
  value_rub: number | null;
}

export interface CouponsListResponse {
  coupons: Coupon[];
  coupon_type?: string | null;  // FIX or FLOAT from amortizations section
}

