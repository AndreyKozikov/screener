import type { ZerocuponRecord } from '../api/zerocupon';
import type { BondListItem } from '../types/bond';
import type { Coupon } from '../types/coupon';
import {
  getLatestZerocuponRecord,
  buildYieldCurveMap,
  interpolateZeroCurveYield,
} from './zerocuponInterpolation';
import { calculateCouponFrequency } from './formatters';

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
 * - t_i is time to payment i in years (calculated as days difference / 365)
 * - M is principal (face value)
 * 
 * Only future coupon payments are included (coupondate > currentDate).
 * Past coupons are completely excluded from calculation.
 * Face value is added only to the last future payment.
 * 
 * @param coupons - Array of coupon payments
 * @param faceValue - Face value of the bond
 * @param currentDate - Current date (analysis date)
 * @param yieldCurveMap - Yield curve map for zero-coupon rates
 * @returns Theoretical clean price (without accrued interest) in absolute value
 */
export const calculateTheoreticalBondPrice = (
  coupons: Coupon[],
  faceValue: number,
  currentDate: Date,
  yieldCurveMap: Map<number, number>
): number | null => {
  if (coupons.length === 0 || faceValue <= 0) return null;

  // Normalize current date to start of day for accurate comparison
  const currentDateNormalized = new Date(currentDate);
  currentDateNormalized.setHours(0, 0, 0, 0);

  // Filter coupons: only include future payments (date > currentDate)
  const futureCoupons = coupons.filter(coupon => {
    if (!coupon.coupondate) return false;
    const couponDate = new Date(coupon.coupondate);
    couponDate.setHours(0, 0, 0, 0);
    return couponDate > currentDateNormalized;
  });

  if (futureCoupons.length === 0) return null;

  // Sort future coupons by date to find the last one
  const sortedFutureCoupons = [...futureCoupons].sort((a, b) => {
    if (!a.coupondate || !b.coupondate) return 0;
    return new Date(a.coupondate).getTime() - new Date(b.coupondate).getTime();
  });

  let theoreticalPrice = 0;

  // Process each future coupon payment
  for (let i = 0; i < sortedFutureCoupons.length; i++) {
    const coupon = sortedFutureCoupons[i];
    if (!coupon.coupondate) continue;

    const couponDate = new Date(coupon.coupondate);
    couponDate.setHours(0, 0, 0, 0);

    // Calculate time to coupon payment in years: difference in days / 365
    const daysToCoupon = (couponDate.getTime() - currentDateNormalized.getTime()) / (1000 * 60 * 60 * 24);
    const yearsToCoupon = daysToCoupon / 365;

    if (yearsToCoupon <= 0) continue;

    // Get spot rate for this period (with interpolation if needed)
    const spotRate = interpolateZeroCurveYield(yieldCurveMap, yearsToCoupon);
    if (spotRate === null) return null;

    // Get coupon value (in currency units, not percentage)
    const couponValue = coupon.value_rub ?? coupon.value ?? 0;
    if (couponValue <= 0) continue;

    // Check if this is the last future payment - add face value to it
    const isLastPayment = i === sortedFutureCoupons.length - 1;
    const totalPayment = couponValue + (isLastPayment ? faceValue : 0);

    // Discount coupon payment: CF / (1 + z)^t
    // Convert spot rate from percentage to decimal
    const spotRateDecimal = spotRate / 100;
    const discountedPayment = totalPayment / Math.pow(1 + spotRateDecimal, yearsToCoupon);
    theoreticalPrice += discountedPayment;
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
 * Only future coupon payments are included (coupondate > currentDate).
 * Past coupons are completely excluded from calculation.
 * Face value is added only to the last future payment.
 * Time to payment is calculated as (days difference) / 365.
 * 
 * @param coupons - List of coupon payments
 * @param faceValue - Face value of the bond
 * @param currentPrice - Current bond price (dirty price including accrued interest)
 * @param currentDate - Current date (analysis date)
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

  // Normalize current date to start of day for accurate comparison
  const currentDateNormalized = new Date(currentDate);
  currentDateNormalized.setHours(0, 0, 0, 0);

  // Filter coupons: only include future payments (date > currentDate)
  const futureCoupons = coupons.filter(coupon => {
    if (!coupon.coupondate) return false;
    const couponDate = new Date(coupon.coupondate);
    couponDate.setHours(0, 0, 0, 0);
    return couponDate > currentDateNormalized;
  });

  if (futureCoupons.length === 0) return null;

  // Sort future coupons by date
  const sortedFutureCoupons = [...futureCoupons].sort((a, b) => {
    if (!a.coupondate || !b.coupondate) return 0;
    return new Date(a.coupondate).getTime() - new Date(b.coupondate).getTime();
  });

  const maxIterations = 100;
  const tolerance = 1e-6;
  let ytm = initialGuess;

  for (let i = 0; i < maxIterations; i++) {
    let price = 0;
    let priceDerivative = 0;

    // Calculate price and its derivative using only future coupons
    for (let j = 0; j < sortedFutureCoupons.length; j++) {
      const coupon = sortedFutureCoupons[j];
      if (!coupon.coupondate) continue;

      const couponDate = new Date(coupon.coupondate);
      couponDate.setHours(0, 0, 0, 0);

      // Calculate time to coupon payment in years: difference in days / 365
      const daysToCoupon = (couponDate.getTime() - currentDateNormalized.getTime()) / (1000 * 60 * 60 * 24);
      const yearsToCoupon = daysToCoupon / 365;

      if (yearsToCoupon <= 0) continue;

      const couponValue = coupon.value_rub ?? coupon.value ?? 0;
      if (couponValue <= 0) continue;

      // Check if this is the last future payment - add face value to it
      const isLastPayment = j === sortedFutureCoupons.length - 1;
      const totalPayment = couponValue + (isLastPayment ? faceValue : 0);

      const discountFactor = Math.pow(1 + ytm, yearsToCoupon);
      price += totalPayment / discountFactor;
      priceDerivative -= (totalPayment * yearsToCoupon) / (discountFactor * (1 + ytm));
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
 * Calculate G-spread (government spread) for a bond
 * 
 * This calculates the theoretical YTM based on zero-coupon yield curve (KBD)
 * and compares it with the actual market YTM.
 * 
 * G-spread = Actual_YTM - Theoretical_YTM
 * 
 * Where Theoretical_YTM is calculated from the theoretical bond price,
 * which is derived by discounting all future coupon payments and face value
 * using spot rates from the zero-coupon yield curve (interpolated as needed).
 * 
 * Both theoretical and market prices use dirty price (clean price + accrued interest)
 * to ensure consistent comparison.
 * 
 * Only future coupon payments are included in calculation (coupondate > currentDate).
 * Past coupons are completely excluded. Face value is added only to the last future payment.
 * Time to payment is calculated as (days difference) / 365.
 * 
 * Note: This is NOT Z-spread. Z-spread would require finding a constant spread added
 * to all spot rates that makes the theoretical price equal to market price.
 * This function calculates G-spread, which is the difference between actual YTM
 * and theoretical YTM derived from the zero-coupon curve.
 * 
 * @param bond - Bond data
 * @param coupons - Array of coupon payments
 * @param zerocuponData - Zero-coupon yield curve data (KBD)
 * @param currentDate - Current date (analysis date). If not provided, uses current date.
 * @returns G-spread = Actual YTM - Theoretical YTM (in percentage points)
 */
export const calculateGSpread = (
  bond: BondListItem,
  coupons: Coupon[],
  zerocuponData: ZerocuponRecord[],
  currentDate: Date = new Date()
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
  // Market clean price in absolute terms = PREVPRICE * FACEVALUE / 100
  const marketPricePercent = bond.PREVPRICE;
  if (!marketPricePercent || marketPricePercent <= 0) {
    return null;
  }

  // Get accrued interest (НКД - накопленный купонный доход)
  // This will be added to theoretical clean price for comparison with market dirty price
  const accruedInterest = bond.ACCRUEDINT ?? 0;
  
  // Calculate theoretical clean price using zero-coupon yield curve (KBD)
  // Theoretical price = Σ(CF_i / (1 + z_i)^t_i) + M / (1 + z_n)^t_n
  // where z_i are spot rates from KBD curve
  // Only future coupons are included (coupondate > currentDate)
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
  // Market dirty price = Market clean price (PREVPRICE * FACEVALUE / 100) + accrued interest
  const theoreticalDirtyPrice = theoreticalCleanPrice + accruedInterest;

  // Calculate theoretical YTM from theoretical dirty price
  // The dirty price already includes accrued interest, so all coupons are discounted in full
  // Only future coupons are included in calculation
  // This theoretical YTM represents the yield that would result from pricing the bond
  // using the zero-coupon yield curve (KBD) without any spread adjustment
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

  // Get actual market YTM (which should be calculated based on dirty price in the source data)
  const actualYTM = bond.YIELDATPREVWAPRICE;
  if (actualYTM === null || actualYTM === undefined) {
    return null;
  }

  // Calculate G-spread: Actual YTM - Theoretical YTM
  // This is the premium/discount relative to the zero-coupon yield curve
  // Positive value indicates premium for credit risk and liquidity risk
  // Negative value indicates discount (bond trades cheaper than theoretical price)
  const gSpread = actualYTM - theoreticalYTM;

  // Round to 2 decimal places
  return Math.round(gSpread * 100) / 100;
};

/**
 * Format G-spread as "+X.XX%" or "-X.XX%" or "0.00%"
 */
export const formatGSpread = (spread: number | null): string => {
  if (spread === null || isNaN(spread)) return '—';

  const rounded = Math.round(spread * 100) / 100;

  if (rounded === 0) {
    return '0.00%';
  }

  const sign = rounded >= 0 ? '+' : '';
  return `${sign}${rounded.toFixed(2)}%`;
};

/**
 * Calculate theoretical bond price with Z-spread added to spot rates
 * 
 * This function implements the Z-spread calculation according to the Moscow Exchange (MOEX)
 * Zero-Coupon Yield Curve Methodology. The methodology treats the yield curve as a set of
 * effective annual zero rates (effective annual spot rates).
 * 
 * Formula: Price = Σ(CF_i / (1 + r(t_i) + z)^t_i) + M / (1 + r(t_n) + z)^t_n
 * 
 * where:
 * - CF_i is coupon payment at period i
 * - r(t_i) is effective annual spot rate from MOEX KBD curve for time t_i (in years)
 * - z is the Z-spread (additively added to effective annual spot rate)
 * - t_i is time to payment i in years
 * - M is principal (face value)
 * 
 * IMPORTANT METHODOLOGICAL NOTES:
 * - MOEX methodology interprets KBD as effective annual spot rates, NOT nominal rates
 * - The discounting formula: (1 + r(t_i) + z)^(-t_i) where r(t_i) is effective annual spot rate
 * - Division by coupon frequency and multiplication of exponent by frequency are PROHIBITED
 * - Z-spread is added additively to the effective annual spot rate
 * - Alternative interpretations (nominal rates, period-based compounding) are methodologically incorrect
 * 
 * Only future coupon payments are included (coupondate > currentDate).
 * 
 * @param coupons - Array of coupon payments
 * @param faceValue - Face value of the bond
 * @param currentDate - Current date (analysis date)
 * @param yieldCurveMap - Yield curve map for zero-coupon rates (effective annual spot rates in percentage)
 * @param zSpread - Z-spread to add to spot rates (in decimal, e.g., 0.01 for 1%)
 * @param frequency - Coupon payment frequency per year (used only for cash flow structure, NOT for discounting)
 * @returns Theoretical price with Z-spread
 */
const calculatePriceWithZSpread = (
  coupons: Coupon[],
  faceValue: number,
  currentDate: Date,
  yieldCurveMap: Map<number, number>,
  zSpread: number,
  frequency: number
): number | null => {
  if (coupons.length === 0 || faceValue <= 0) return null;

  // Normalize current date to start of day for accurate comparison
  const currentDateNormalized = new Date(currentDate);
  currentDateNormalized.setHours(0, 0, 0, 0);

  // Filter coupons: only include future payments (date > currentDate)
  const futureCoupons = coupons.filter(coupon => {
    if (!coupon.coupondate) return false;
    const couponDate = new Date(coupon.coupondate);
    couponDate.setHours(0, 0, 0, 0);
    return couponDate > currentDateNormalized;
  });

  if (futureCoupons.length === 0) return null;

  // Sort future coupons by date to find the last one
  const sortedFutureCoupons = [...futureCoupons].sort((a, b) => {
    if (!a.coupondate || !b.coupondate) return 0;
    return new Date(a.coupondate).getTime() - new Date(b.coupondate).getTime();
  });

  let price = 0;

  // Process each future coupon payment
  for (let i = 0; i < sortedFutureCoupons.length; i++) {
    const coupon = sortedFutureCoupons[i];
    if (!coupon.coupondate) continue;

    const couponDate = new Date(coupon.coupondate);
    couponDate.setHours(0, 0, 0, 0);

    // Calculate time to coupon payment in years: difference in days / 365
    const daysToCoupon = (couponDate.getTime() - currentDateNormalized.getTime()) / (1000 * 60 * 60 * 24);
    const yearsToCoupon = daysToCoupon / 365;

    if (yearsToCoupon <= 0) continue;

    // Get effective annual spot rate for this period (with interpolation if needed)
    // MOEX KBD provides effective annual zero rates
    const spotRatePercent = interpolateZeroCurveYield(yieldCurveMap, yearsToCoupon);
    if (spotRatePercent === null) return null;

    // Convert effective annual spot rate from percentage to decimal
    const spotRateDecimal = spotRatePercent / 100;
    
    // Add Z-spread additively to effective annual spot rate
    // Formula: (1 + r(t_i) + z)^(-t_i) according to MOEX methodology
    const adjustedRate = spotRateDecimal + zSpread;

    // Get coupon value (in currency units, not percentage)
    const couponValue = coupon.value_rub ?? coupon.value ?? 0;
    if (couponValue <= 0) continue;

    // Check if this is the last future payment - add face value to it
    const isLastPayment = i === sortedFutureCoupons.length - 1;
    const totalPayment = couponValue + (isLastPayment ? faceValue : 0);

    // Discount using MOEX methodology formula: CF_i / (1 + r(t_i) + z)^t_i
    // No division by frequency, no multiplication of exponent by frequency
    // This is the ONLY correct formula according to MOEX methodology
    const discountFactor = Math.pow(1 + adjustedRate, yearsToCoupon);
    const discountedPayment = totalPayment / discountFactor;
    
    price += discountedPayment;
  }

  return price;
};

/**
 * Calculate Z-spread (Zero-Volatility Spread) for a bond using bisection method
 * 
 * This function implements Z-spread calculation strictly according to the Moscow Exchange (MOEX)
 * Zero-Coupon Yield Curve Methodology. The methodology treats KBD as effective annual spot rates.
 * 
 * Z-spread is the constant spread that must be added additively to all effective annual spot rates
 * from the zero-coupon yield curve so that the theoretical bond price equals the market dirty price.
 * 
 * Formula: Market_Dirty_Price = Σ(CF_i / (1 + r(t_i) + z)^t_i) + M / (1 + r(t_n) + z)^t_n
 * 
 * Where:
 * - Market_Dirty_Price = Clean_Price + Accrued_Interest
 * - CF_i are future coupon payments
 * - r(t_i) are effective annual spot rates from MOEX KBD curve for time t_i (in years)
 * - z is the Z-spread (to be found, added additively to effective annual spot rate)
 * - t_i is time to payment i in years
 * - M is face value
 * 
 * METHODOLOGICAL REQUIREMENTS (MOEX):
 * - KBD is interpreted as effective annual zero rates (effective annual spot rates)
 * - Discounting formula: (1 + r(t_i) + z)^(-t_i)
 * - Division by coupon frequency is PROHIBITED
 * - Multiplication of exponent by frequency is PROHIBITED
 * - Z-spread is added additively to effective annual spot rate
 * - Alternative interpretations (nominal rates, period-based compounding) are methodologically incorrect
 * 
 * Uses bisection method to find z such that the difference between calculated and market price < 0.0001
 * 
 * @param bond - Bond data
 * @param coupons - Array of coupon payments
 * @param zerocuponData - Zero-coupon yield curve data (KBD) from MOEX
 * @param currentDate - Current date (analysis date). If not provided, uses current date.
 * @returns Z-spread in percentage points (e.g., 1.5 for 1.5%), or null if calculation fails
 */
export const calculateZSpread = (
  bond: BondListItem,
  coupons: Coupon[],
  zerocuponData: ZerocuponRecord[],
  currentDate: Date = new Date()
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

  // Get coupon frequency
  const frequency = calculateCouponFrequency(bond.COUPONPERIOD);
  if (frequency === null || frequency <= 0) {
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

  // Calculate market clean price in absolute terms
  const marketCleanPrice = (marketPricePercent * bond.FACEVALUE) / 100;

  // Get accrued interest (НКД - накопленный купонный доход)
  const accruedInterest = bond.ACCRUEDINT ?? 0;

  // Calculate market dirty price (clean price + accrued interest)
  const marketDirtyPrice = marketCleanPrice + accruedInterest;

  if (marketDirtyPrice <= 0) {
    return null;
  }

  // Bisection method to find Z-spread
  // Initial range: -0.05 to 0.15 (in decimal: -5% to +15%)
  let zMin = -0.05;
  let zMax = 0.15;
  const tolerance = 0.0001; // 0.01% accuracy (1 basis point in price difference)
  const maxIterations = 100;

  for (let iteration = 0; iteration < maxIterations; iteration++) {
    const zMid = (zMin + zMax) / 2;

    // Calculate price with current Z-spread estimate
    const calculatedPrice = calculatePriceWithZSpread(
      coupons,
      bond.FACEVALUE,
      currentDate,
      yieldCurveMap,
      zMid,
      frequency
    );

    if (calculatedPrice === null) {
      // If calculation fails, try to narrow the range
      // Check if we're at the boundaries
      if (Math.abs(zMid - zMin) < tolerance) {
        zMin = zMid + 0.01;
      } else if (Math.abs(zMid - zMax) < tolerance) {
        zMax = zMid - 0.01;
      } else {
        return null; // Cannot converge
      }
      continue;
    }

    const error = calculatedPrice - marketDirtyPrice;

    // Check if we've found the solution within tolerance
    if (Math.abs(error) < tolerance) {
      // Return Z-spread in percentage points
      return Math.round(zMid * 10000) / 100; // Round to 2 decimal places
    }

    // Adjust range based on error sign
    if (error > 0) {
      // Calculated price is too high, need to increase discount rate (increase Z)
      zMin = zMid;
    } else {
      // Calculated price is too low, need to decrease discount rate (decrease Z)
      zMax = zMid;
    }

    // Check if range is too small (convergence check)
    if (Math.abs(zMax - zMin) < tolerance / 10) {
      // Return the midpoint as best estimate
      return Math.round(zMid * 10000) / 100;
    }
  }

  // If max iterations reached, return the midpoint of final range
  const finalZ = (zMin + zMax) / 2;
  return Math.round(finalZ * 10000) / 100;
};

// Legacy exports for backward compatibility (deprecated - use calculateGSpread and formatGSpread)
/**
 * @deprecated Use calculateGSpread instead. This function is kept for backward compatibility.
 * Note: The legacy calculateZSpread alias now points to calculateGSpread.
 * Use the new calculateZSpread function for true Z-spread calculation.
 */
export const calculateZSpreadLegacy = calculateGSpread;

/**
 * @deprecated Use formatGSpread instead. This function is kept for backward compatibility.
 */
export const formatZSpread = formatGSpread;
