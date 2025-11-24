/**
 * Coupon data interfaces matching backend Pydantic models
 */

export interface Coupon {
  isin: string | null;
  name: string | null;
  issuevalue: number | null;
  coupondate: string | null;
  recorddate: string | null;
  startdate: string | null;
  initialfacevalue: number | null;
  facevalue: number | null;
  faceunit: string | null;
  value: number | null;  // Сумма купона
  valueprc: number | null;  // Ставка купона
  value_rub: number | null;
  secid: string | null;
  primary_boardid: string | null;
}

export interface CouponsListResponse {
  coupons: Coupon[];
}

