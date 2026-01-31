/**
 * Coupon data interfaces matching backend Pydantic models
 */

export interface Coupon {
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
}

export interface CouponsBySecid {
  secid: string;
  coupons: Coupon[];
}

export interface MultipleCouponsResponse {
  data: CouponsBySecid[];
}

