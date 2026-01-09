import type { ZerocuponRecord } from '../api/zerocupon';
import type { BondListItem } from '../types/bond';
import type { Coupon } from '../types/coupon';
import {
  getLatestZerocuponRecord,
  buildYieldCurveMap,
  interpolateZeroCurveYield,
} from './zerocuponInterpolation';

/**
 * Calculate theoretical clean bond price using zero-coupon yield curve
 * Each coupon payment is discounted using its own spot rate
 * 
 * This function returns the clean price (without accrued interest).
 * To get dirty price, add accrued interest to the result.
 * 
 * Formula: CleanPrice = Σ(CF_i / (1 + z_i)^t_i) + M / (1 + z_n)^t_n
 * where:
 * - CF_i is coupon payment at period i
 * - z_i is spot rate for period i
 * - t_i is time to payment i in years
 * - M is principal (face value)
 * 
 * @returns Theoretical clean price (without accrued interest) in absolute value
 */
export const calculateTheoreticalBondPrice = (
  coupons: Coupon[],
  faceValue: number,
  currentDate: Date,
  yieldCurveMap: Map<number, number>
): number | null => {
  if (coupons.length === 0 || faceValue <= 0) return null;

  let theoreticalPrice = 0;

  // Process each coupon payment
  for (const coupon of coupons) {
    if (!coupon.coupondate) continue;

    const couponDate = new Date(coupon.coupondate);
    if (couponDate <= currentDate) continue; // Skip past coupons

    // Calculate time to coupon payment in years
    const daysToCoupon = (couponDate.getTime() - currentDate.getTime()) / (1000 * 60 * 60 * 24);
    const yearsToCoupon = daysToCoupon / 365;

    if (yearsToCoupon <= 0) continue;

    // Get spot rate for this period (with interpolation if needed)
    const spotRate = interpolateZeroCurveYield(yieldCurveMap, yearsToCoupon);
    if (spotRate === null) return null;

    // Get coupon value (in currency units, not percentage)
    const couponValue = coupon.value_rub ?? coupon.value ?? 0;
    if (couponValue <= 0) continue;

    // Discount coupon payment: CF / (1 + z)^t
    // Convert spot rate from percentage to decimal
    const spotRateDecimal = spotRate / 100;
    const discountedCoupon = couponValue / Math.pow(1 + spotRateDecimal, yearsToCoupon);
    theoreticalPrice += discountedCoupon;
  }

  // Add principal payment at maturity (use the last coupon date as maturity date)
  // Sort coupons by date to find the last one
  const sortedCoupons = [...coupons].sort((a, b) => {
    if (!a.coupondate || !b.coupondate) return 0;
    return new Date(a.coupondate).getTime() - new Date(b.coupondate).getTime();
  });
  
  const lastCoupon = sortedCoupons[sortedCoupons.length - 1];
  if (lastCoupon?.coupondate) {
    const maturityDate = new Date(lastCoupon.coupondate);
    const daysToMaturity = (maturityDate.getTime() - currentDate.getTime()) / (1000 * 60 * 60 * 24);
    const yearsToMaturity = daysToMaturity / 365;

    if (yearsToMaturity > 0) {
      const spotRate = interpolateZeroCurveYield(yieldCurveMap, yearsToMaturity);
      if (spotRate === null) return null;

      const spotRateDecimal = spotRate / 100;
      const discountedPrincipal = faceValue / Math.pow(1 + spotRateDecimal, yearsToMaturity);
      theoreticalPrice += discountedPrincipal;
    }
  }

  return theoreticalPrice;
};

/**
 * Calculate YTM from bond price using Newton-Raphson method
 * 
 * Formula: DirtyPrice = Σ(CF_i / (1 + YTM)^t_i) + M / (1 + YTM)^t_n
 * where DirtyPrice = CleanPrice + AccruedInterest
 * 
 * When using dirty price, all coupon payments are discounted in full.
 * The accrued interest is already included in the dirty price.
 * 
 * @param coupons - List of coupon payments
 * @param faceValue - Face value of the bond
 * @param currentPrice - Current bond price (dirty price including accrued interest)
 * @param currentDate - Current date
 * @param accruedInterest - Accrued interest (НКД) - used for reference only, not subtracted from coupons
 * @param initialGuess - Initial guess for YTM (default 5%)
 */
const calculateYTMFromPrice = (
  coupons: Coupon[],
  faceValue: number,
  currentPrice: number,
  currentDate: Date,
  _accruedInterest: number = 0,
  initialGuess: number = 0.05 // 5% initial guess
): number | null => {
  if (coupons.length === 0 || faceValue <= 0 || currentPrice <= 0) return null;

  const maxIterations = 100;
  const tolerance = 1e-6;
  let ytm = initialGuess;

  // Sort coupons by date
  const sortedCoupons = [...coupons].sort((a, b) => {
    if (!a.coupondate || !b.coupondate) return 0;
    return new Date(a.coupondate).getTime() - new Date(b.coupondate).getTime();
  });

  for (let i = 0; i < maxIterations; i++) {
    let price = 0;
    let priceDerivative = 0;

    // Calculate price and its derivative
    // When using dirty price, all coupon payments are discounted in full
    // The buyer pays accrued interest upfront and receives full coupons later
    for (const coupon of sortedCoupons) {
      if (!coupon.coupondate) continue;

      const couponDate = new Date(coupon.coupondate);
      if (couponDate <= currentDate) continue;

      const daysToCoupon = (couponDate.getTime() - currentDate.getTime()) / (1000 * 60 * 60 * 24);
      const yearsToCoupon = daysToCoupon / 365;

      if (yearsToCoupon <= 0) continue;

      const couponValue = coupon.value_rub ?? coupon.value ?? 0;
      if (couponValue <= 0) continue;

      const discountFactor = Math.pow(1 + ytm, yearsToCoupon);
      price += couponValue / discountFactor;
      priceDerivative -= (couponValue * yearsToCoupon) / (discountFactor * (1 + ytm));
    }

    // Add principal
    const lastCoupon = sortedCoupons[sortedCoupons.length - 1];
    if (lastCoupon?.coupondate) {
      const maturityDate = new Date(lastCoupon.coupondate);
      const daysToMaturity = (maturityDate.getTime() - currentDate.getTime()) / (1000 * 60 * 60 * 24);
      const yearsToMaturity = daysToMaturity / 365;

      if (yearsToMaturity > 0) {
        const discountFactor = Math.pow(1 + ytm, yearsToMaturity);
        price += faceValue / discountFactor;
        priceDerivative -= (faceValue * yearsToMaturity) / (discountFactor * (1 + ytm));
      }
    }

    // Newton-Raphson iteration
    const error = price - currentPrice;
    if (Math.abs(error) < tolerance) {
      return ytm * 100; // Convert to percentage
    }

    if (Math.abs(priceDerivative) < tolerance) {
      break; // Derivative too small, cannot converge
    }

    ytm = ytm - error / priceDerivative;

    // Ensure YTM is reasonable
    if (ytm < -0.5 || ytm > 2) {
      break; // Unreasonable value
    }
  }

  return ytm * 100; // Convert to percentage
};

/**
 * Calculate Z-spread (zero-coupon spread) for a bond
 * 
 * This calculates the theoretical yield based on zero-coupon curve
 * and compares it with the actual YTM
 * 
 * Both theoretical and market prices use dirty price (clean price + accrued interest)
 * to ensure consistent comparison
 * 
 * Returns: Actual YTM - Theoretical YTM (in percentage points)
 */
export const calculateZSpread = (
  bond: BondListItem,
  coupons: Coupon[],
  zerocuponData: ZerocuponRecord[]
): number | null => {
  // Only calculate for fixed coupon bonds
  if (bond.BONDTYPE43 !== 'Фикс с известным купоном') {
    return null;
  }

  // Check required data
  if (!bond.MATDATE || !bond.FACEVALUE || bond.FACEVALUE <= 0) {
    return null;
  }

  if (coupons.length === 0) {
    return null;
  }

  // Get latest zero-coupon yield curve
  const latestRecord = getLatestZerocuponRecord(zerocuponData);
  if (!latestRecord) {
    return null;
  }

  // Build yield curve map
  const yieldCurveMap = buildYieldCurveMap(latestRecord);
  if (yieldCurveMap.size === 0) {
    return null;
  }

  // Get current market price (as percentage of face value) - clean price
  const marketPricePercent = bond.PREVPRICE;
  if (!marketPricePercent || marketPricePercent <= 0) {
    return null;
  }

  // Get accrued interest (НКД)
  const accruedInterest = bond.ACCRUEDINT ?? 0;
  
  // Calculate theoretical clean price using zero-coupon curve
  const currentDate = new Date();
  const theoreticalCleanPrice = calculateTheoreticalBondPrice(
    coupons,
    bond.FACEVALUE,
    currentDate,
    yieldCurveMap
  );

  if (theoreticalCleanPrice === null || theoreticalCleanPrice <= 0) {
    return null;
  }

  // Calculate theoretical dirty price (theoretical clean price + accrued interest)
  // This ensures consistent comparison with market dirty price
  const theoreticalDirtyPrice = theoreticalCleanPrice + accruedInterest;

  // Calculate theoretical YTM from theoretical dirty price
  // The dirty price already includes accrued interest, so all coupons are discounted in full
  const theoreticalYTM = calculateYTMFromPrice(
    coupons,
    bond.FACEVALUE,
    theoreticalDirtyPrice,
    currentDate,
    accruedInterest // Passed for reference, not used in calculation
  );

  if (theoreticalYTM === null) {
    return null;
  }

  // Get actual YTM (which should be calculated based on dirty price in the source data)
  const actualYTM = bond.YIELDATPREVWAPRICE;
  if (actualYTM === null || actualYTM === undefined) {
    return null;
  }

  // Calculate spread: Actual YTM - Theoretical YTM
  const spread = actualYTM - theoreticalYTM;

  // Round to 2 decimal places
  return Math.round(spread * 100) / 100;
};

/**
 * Format Z-spread as "+X.XX%" or "-X.XX%" or "0.00%"
 */
export const formatZSpread = (spread: number | null): string => {
  if (spread === null || isNaN(spread)) return '—';

  const rounded = Math.round(spread * 100) / 100;

  if (rounded === 0) {
    return '0.00%';
  }

  const sign = rounded >= 0 ? '+' : '';
  return `${sign}${rounded.toFixed(2)}%`;
};

