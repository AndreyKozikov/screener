import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams, IHeaderParams } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import '../bonds/ag-grid-tooltips.css';
import {
  Box,
  Typography,
  Tooltip,
  Card,
  CardContent,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tabs,
  Tab,
} from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { fetchBonds } from '../../api/bonds';
import { getEmitentList } from '../../api/emitent';
import { formatNumber, calculateCouponFrequency } from '../../utils/formatters';
import { fetchZerocuponData, type ZerocuponRecord } from '../../api/zerocupon';
import {
  getLatestZerocuponRecord,
  buildYieldCurveMap,
  interpolateZeroCurveYield,
  calculateSpread,
  formatSpread,
} from '../../utils/zerocuponInterpolation';
import { calculateZSpread, formatZSpread } from '../../utils/zSpreadCalculation';
import { fetchBondCoupons } from '../../api/bonds';
import type { Coupon } from '../../types/coupon';
import dayjs from 'dayjs';
import type { BondListItem } from '../../types/bond';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { useFiltersStore } from '../../stores/filtersStore';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  Tooltip as RechartsTooltip,
  ScatterChart,
  Scatter,
  Cell,
  LabelList,
} from 'recharts';
import { CHART_CONFIG } from '../../utils/constants';
import * as regression from 'regression';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

interface ComparisonRow {
  name: string;
  ticker: string;
  maturity: string;
  price: string;
  ytm: string;
  coupon: string;
  couponToPrice: string;
  regularDuration: string;
  duration: string;
  convexity: string;
  priceChange: string;
  spread: string;
  zSpread: string;
  secid: string;
}

/**
 * SpreadAnalysis Component
 * 
 * Displays spread curve analysis for bonds grouped by emitent
 */
export const SpreadAnalysis: React.FC = () => {
  const [selectedEmitent, setSelectedEmitent] = useState<string>('');
  const [emitentOptions, setEmitentOptions] = useState<string[]>([]);
  const [isLoadingEmitents, setIsLoadingEmitents] = useState(false);
  const [bonds, setBonds] = useState<BondListItem[]>([]);
  const [isLoadingBonds, setIsLoadingBonds] = useState(false);
  const [zerocuponData, setZerocuponData] = useState<ZerocuponRecord[]>([]);
  const [isLoadingZerocupon, setIsLoadingZerocupon] = useState(false);
  const [couponsData, setCouponsData] = useState<Map<string, Coupon[]>>(new Map());
  const [isLoadingCoupons, setIsLoadingCoupons] = useState(false);
  const gridRef = useRef<AgGridReact<ComparisonRow>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);
  const filters = useFiltersStore((state) => state.filters);
  const [currentTab, setCurrentTab] = useState(0);

  // Load emitent list on mount
  useEffect(() => {
    const loadEmitents = async () => {
      setIsLoadingEmitents(true);
      try {
        const response = await getEmitentList();
        setEmitentOptions(response.emitents);
        // Don't auto-select - user should choose from empty state
      } catch (error) {
        console.error('Error loading emitents:', error);
        setEmitentOptions([]);
      } finally {
        setIsLoadingEmitents(false);
      }
    };

    void loadEmitents();
  }, []);

  // Load bonds when emitent is selected
  useEffect(() => {
    if (!selectedEmitent || selectedEmitent === '') {
      setBonds([]);
      return;
    }

    const loadBonds = async () => {
      setIsLoadingBonds(true);
      try {
        const response = await fetchBonds(filters, selectedEmitent);
        setBonds(response.bonds);
      } catch (error) {
        console.error('Error loading bonds:', error);
        setBonds([]);
      } finally {
        setIsLoadingBonds(false);
      }
    };

    void loadBonds();
  }, [selectedEmitent, filters]);

  // Load zero-coupon yield curve data
  useEffect(() => {
    if (bonds.length === 0) return;

    const loadZerocuponData = async () => {
      try {
        setIsLoadingZerocupon(true);
        const today = dayjs();
        const oneYearAgo = today.subtract(1, 'year');

        const dateFrom = oneYearAgo.format('DD.MM.YYYY');
        const dateTo = today.format('DD.MM.YYYY');

        const response = await fetchZerocuponData(dateFrom, dateTo);
        setZerocuponData(response.data);
      } catch (error) {
        console.error('Error loading zerocupon data:', error);
        setZerocuponData([]);
      } finally {
        setIsLoadingZerocupon(false);
      }
    };

    void loadZerocuponData();
  }, [bonds.length]);

  // Load coupons data for fixed coupon bonds
  useEffect(() => {
    if (bonds.length === 0) return;

    const loadCouponsData = async () => {
      try {
        setIsLoadingCoupons(true);
        const couponsMap = new Map<string, Coupon[]>();

        const fixedCouponBonds = bonds.filter(
          bond => bond.BONDTYPE43 === 'Фикс с известным купоном'
        );

        const couponPromises = fixedCouponBonds.map(async (bond) => {
          try {
            const response = await fetchBondCoupons(bond.SECID, false);
            if (response.coupons && response.coupons.length > 0) {
              couponsMap.set(bond.SECID, response.coupons);
            }
          } catch (error) {
            console.error(`Error loading coupons for ${bond.SECID}:`, error);
          }
        });

        await Promise.all(couponPromises);
        setCouponsData(couponsMap);
      } catch (error) {
        console.error('Error loading coupons data:', error);
        setCouponsData(new Map());
      } finally {
        setIsLoadingCoupons(false);
      }
    };

    void loadCouponsData();
  }, [bonds]);

  // Calculate years until maturity
  const calculateYearsToMaturity = (matDate: string | null): number | null => {
    if (!matDate) return null;
    
    try {
      const today = new Date();
      const maturity = new Date(matDate);
      if (isNaN(maturity.getTime())) return null;
      
      const diffTime = maturity.getTime() - today.getTime();
      const diffYears = diffTime / (1000 * 60 * 60 * 24 * 365);
      
      return diffYears;
    } catch {
      return null;
    }
  };

  const formatMaturity = (matDate: string | null): string => {
    if (!matDate) return '—';
    try {
      const yearsToMaturity = calculateYearsToMaturity(matDate);
      if (yearsToMaturity === null) return '—';
      const roundedYears = Math.round(yearsToMaturity * 10) / 10;
      return roundedYears.toFixed(1);
    } catch {
      return '—';
    }
  };

  // Check if bond has call or put options
  // Bonds with options should be excluded from metric calculations
  const hasOptions = (bond: BondListItem): boolean => {
    // Check if bond has call option date or put option date
    return (bond.CALLOPTIONDATE !== null && bond.CALLOPTIONDATE !== undefined && bond.CALLOPTIONDATE !== '') ||
           (bond.PUTOPTIONDATE !== null && bond.PUTOPTIONDATE !== undefined && bond.PUTOPTIONDATE !== '');
  };

  // Check if metrics are applicable for this bond
  // Metrics (modified duration, convexity, price change, spread, z-spread) are only applicable for:
  // Fixed coupon bonds with known coupon rate (BONDTYPE43 === "Фикс с известным купоном")
  // AND without call or put options
  const isFixedCouponBond = (bond: BondListItem): boolean => {
    // Check if bond type is "Фикс с известным купоном" and has no options
    return bond.BONDTYPE43 === 'Фикс с известным купоном' && !hasOptions(bond);
  };

  // Calculate regular duration in years
  const calculateRegularDuration = (bond: BondListItem): number | null => {
    if (bond.DURATION === null || bond.DURATION === undefined || bond.DURATION === 0) {
      return null;
    }
    
    // Convert from days to years (DURATION уже в днях)
    return bond.DURATION / 365;
  };

  // Calculate modified duration in years
  // Modified Duration is only applicable for fixed coupon bonds with known coupon rate
  // According to financial theory, modified duration directly estimates percentage price change
  // per 100 basis points change in yield
  const calculateModifiedDuration = (bond: BondListItem): number | null => {
    // Check if modified duration is applicable for this bond type
    if (!isFixedCouponBond(bond)) {
      return null;
    }
    
    if (bond.DURATION === null || bond.DURATION === undefined || bond.DURATION === 0) {
      return null;
    }
    
    // Convert from days to years (DURATION уже в днях)
    const durationYears = bond.DURATION / 365;
    
    // Modified Duration = D / (1 + YTM/100)
    // Where D is Macaulay duration in years
    if (bond.YIELDATPREVWAPRICE === null || bond.YIELDATPREVWAPRICE === undefined) {
      return durationYears;
    }
    
    const ytmDecimal = bond.YIELDATPREVWAPRICE / 100;
    const modifiedDuration = durationYears / (1 + ytmDecimal);
    
    return modifiedDuration;
  };

  // Calculate convexity for fixed coupon bonds
  // Convexity measures the sensitivity of duration to changes in yield
  // Only applicable for fixed coupon bonds with known coupon rate
  const calculateConvexity = (bond: BondListItem): number | null => {
    // Check if convexity is applicable for this bond type
    if (!isFixedCouponBond(bond)) {
      return null;
    }

    // Required inputs
    const faceValue = bond.FACEVALUE;
    const marketPricePct = bond.PREVPRICE;
    const couponRate = bond.COUPONPERCENT;
    const yearsToMaturity = calculateYearsToMaturity(bond.MATDATE);
    const frequency = calculateCouponFrequency(bond.COUPONPERIOD);
    const ytmAnnual = bond.YIELDATPREVWAPRICE;
    const accruedInterest = bond.ACCRUEDINT ?? 0;

    // Validate required inputs
    if (
      faceValue === null || faceValue <= 0 ||
      marketPricePct === null || marketPricePct <= 0 ||
      couponRate === null || couponRate < 0 ||
      yearsToMaturity === null || yearsToMaturity <= 0 ||
      frequency === null || frequency <= 0 ||
      ytmAnnual === null || ytmAnnual < 0
    ) {
      return null;
    }

    // Step 1: Calculate Dirty Price
    // Dirty_Price = (face_value * market_price_pct / 100) + accrued_interest
    const dirtyPrice = (faceValue * marketPricePct / 100) + accruedInterest;

    if (dirtyPrice <= 0) {
      return null;
    }

    // Step 2: Calculate rate per period
    // Ставка за период (y) = ytm_annual / frequency
    const ytmDecimal = ytmAnnual / 100;
    const y = ytmDecimal / frequency;

    // Step 3: Calculate total number of periods
    // Общее количество периодов (n) = years_to_maturity * frequency
    const n = Math.ceil(yearsToMaturity * frequency); // Round up to include all periods

    // Step 4: Calculate coupon payment per period
    // Размер купона = (face_value * coupon_rate) / frequency
    const couponRateDecimal = couponRate / 100;
    const couponPayment = (faceValue * couponRateDecimal) / frequency;

    // Step 5: Loop through all coupon periods and calculate convexity sum
    let sum = 0;
    for (let t = 1; t <= n; t++) {
      // Calculate Cash Flow (CF)
      // CF последнего периода = Купон + Номинал. Остальные CF = только Купон
      const cf = t === n ? couponPayment + faceValue : couponPayment;

      // Calculate discount factor: (1 + y)^t
      const discountFactor = Math.pow(1 + y, t);

      // Calculate term: (CF / (1 + y)^t) * (t^2 + t)
      const term = (cf / discountFactor) * (t * t + t);
      sum += term;
    }

    // Step 6: Calculate final Convexity
    // Convexity = (Сумма слагаемых) / (Dirty_Price * (1 + y)^2 * frequency^2)
    const convexity = sum / (dirtyPrice * Math.pow(1 + y, 2) * frequency * frequency);

    return convexity;
  };

  // Calculate price change for two scenarios: up_shock (+1%) and down_shock (-1%)
  // Formula: ΔP% = -(MD × dy) + (0.5 × Convexity × dy²)
  // Returns an object with upShock (for +1% rate change) and downShock (for -1% rate change)
  // This calculation is only valid for fixed coupon bonds with known coupon rate
  const calculatePriceChange = (bond: BondListItem): { upShock: number; downShock: number } | null => {
    // Check if price change calculation is applicable for this bond type
    if (!isFixedCouponBond(bond)) {
      return null;
    }
    
    const md = calculateModifiedDuration(bond);
    if (md === null) return null;
    
    // Get convexity value
    const convexity = calculateConvexity(bond);
    if (convexity === null) {
      // If convexity cannot be calculated, fall back to duration-only approximation
      // For up_shock (dy = 0.01): -(MD * 0.01) = -MD * 0.01
      // For down_shock (dy = -0.01): -(MD * -0.01) = MD * 0.01
      const upShock = -md * 0.01 * 100;  // Negative (loss) when rates increase
      const downShock = md * 0.01 * 100; // Positive (gain) when rates decrease
      return { upShock, downShock };
    }
    
    // Calculate price change for up_shock: dy = 0.01 (+1% rate change)
    // Formula: -(MD × 0.01) + (0.5 × Convexity × (0.01)²)
    const dyUp = 0.01;
    const linearPartUp = -(md * dyUp);
    const convexityAdjustmentUp = 0.5 * convexity * (dyUp * dyUp);
    const upShock = (linearPartUp + convexityAdjustmentUp) * 100; // Negative (loss)
    
    // Calculate price change for down_shock: dy = -0.01 (-1% rate change)
    // Formula: -(MD × -0.01) + (0.5 × Convexity × (-0.01)²) = (MD × 0.01) + (0.5 × Convexity × 0.0001)
    const dyDown = -0.01;
    const linearPartDown = -(md * dyDown);
    const convexityAdjustmentDown = 0.5 * convexity * (dyDown * dyDown);
    const downShock = (linearPartDown + convexityAdjustmentDown) * 100; // Positive (gain)
    
    return { upShock, downShock };
  };

  // Format convexity value
  const formatConvexity = (value: number | null): string => {
    if (value === null || value === undefined || isNaN(value)) return '—';
    
    // Round to 2 decimal places
    return value.toFixed(2);
  };

  // Format price change as "{убыток}% / {прибыль}%"
  // Shows two scenarios: up_shock (loss when rates increase) and down_shock (gain when rates decrease)
  const formatPriceChange = (value: { upShock: number; downShock: number } | null): string => {
    if (value === null || value === undefined) return '—';
    
    // Round both values to 2 decimal places
    const upShockRounded = Math.round(value.upShock * 100) / 100;
    const downShockRounded = Math.round(value.downShock * 100) / 100;
    
    // Format upShock (should be negative - loss when rates increase)
    // Always show with minus sign (if somehow positive, show as negative)
    const upShockStr = upShockRounded < 0 
      ? `${upShockRounded.toFixed(2)}%` 
      : `-${Math.abs(upShockRounded).toFixed(2)}%`;
    
    // Format downShock (should be positive - gain when rates decrease)
    // Always show with plus sign if positive
    const downShockStr = downShockRounded > 0 
      ? `+${downShockRounded.toFixed(2)}%` 
      : `${downShockRounded.toFixed(2)}%`;
    
    return `${upShockStr} / ${downShockStr}`;
  };

  // Get color for spread value (positive = green, negative = red/gray)
  const getSpreadColor = (spreadStr: string): string => {
    if (spreadStr === '—' || spreadStr === '' || !spreadStr) return 'inherit';
    
    // Parse spread string (e.g., "+1.23%" or "-1.23%" or "0.00%")
    const cleaned = spreadStr.replace('%', '').replace('+', '').trim();
    const numericValue = parseFloat(cleaned);
    
    if (isNaN(numericValue)) return 'inherit';
    
    // Positive values = green (premium is good for investor)
    if (numericValue > 0) {
      return '#4CAF50'; // Green
    }
    
    // Negative values = red (no premium)
    if (numericValue < 0) {
      return '#E53935'; // Red
    }
    
    // Zero = default color
    return 'inherit';
  };

  // Check if spread value is non-zero and valid
  const isSpreadNonZero = (spreadStr: string): boolean => {
    if (spreadStr === '—' || spreadStr === '' || !spreadStr) return false;
    
    const cleaned = spreadStr.replace('%', '').replace('+', '').trim();
    const numericValue = parseFloat(cleaned);
    
    if (isNaN(numericValue)) return false;
    
    return numericValue !== 0;
  };

  // Calculate coupon yield to current price
  const calculateCouponToPrice = (bond: BondListItem): number | null => {
    if (
      bond.COUPONPERCENT === null || bond.COUPONPERCENT === undefined ||
      bond.PREVPRICE === null || bond.PREVPRICE === undefined ||
      bond.PREVPRICE === 0
    ) {
      return null;
    }
    
    // Coupon yield to current price = (Coupon % / Current Price %) * 100
    return (bond.COUPONPERCENT / bond.PREVPRICE) * 100;
  };

  // Prepare comparison data
  const comparisonData: ComparisonRow[] = useMemo(() => {
    if (bonds.length === 0) return [];

    // Get latest zero-coupon yield curve record
    const latestRecord = getLatestZerocuponRecord(zerocuponData);
    if (!latestRecord) {
      // If no zerocupon data, return data without spread
      return bonds.map((bond) => {
        const price = bond.PREVPRICE !== null && bond.PREVPRICE !== undefined
          ? formatNumber(bond.PREVPRICE, 2)
          : '—';
        
        const ytm = bond.YIELDATPREVWAPRICE !== null && bond.YIELDATPREVWAPRICE !== undefined
          ? formatNumber(bond.YIELDATPREVWAPRICE, 2)
          : '—';
        
        const coupon = bond.COUPONPERCENT !== null && bond.COUPONPERCENT !== undefined
          ? formatNumber(bond.COUPONPERCENT, 2)
          : '—';
        
        const couponToPrice = calculateCouponToPrice(bond);
        const couponToPriceStr = couponToPrice !== null
          ? formatNumber(couponToPrice, 2)
          : '—';
        
        const regularDuration = calculateRegularDuration(bond);
        const regularDurationStr = regularDuration !== null
          ? formatNumber(regularDuration, 2)
          : '—';
        
        const duration = calculateModifiedDuration(bond);
        const durationStr = duration !== null
          ? formatNumber(duration, 2)
          : '—';
        
        const convexity = formatConvexity(calculateConvexity(bond));
        
        const priceChange = formatPriceChange(calculatePriceChange(bond));
        
        return {
          name: bond.SHORTNAME || '—',
          ticker: bond.SECID || '—',
          maturity: formatMaturity(bond.MATDATE),
          price,
          ytm,
          coupon,
          couponToPrice: couponToPriceStr,
          regularDuration: regularDurationStr,
          duration: durationStr,
          convexity,
          priceChange,
          spread: '—',
          zSpread: '—',
          secid: bond.SECID,
        };
      });
    }

    // Build yield curve map
    const yieldCurveMap = buildYieldCurveMap(latestRecord);

    return bonds.map((bond) => {
      const price = bond.PREVPRICE !== null && bond.PREVPRICE !== undefined
        ? formatNumber(bond.PREVPRICE, 2)
        : '—';
      
      const ytm = bond.YIELDATPREVWAPRICE !== null && bond.YIELDATPREVWAPRICE !== undefined
        ? formatNumber(bond.YIELDATPREVWAPRICE, 2)
        : '—';
      
      const coupon = bond.COUPONPERCENT !== null && bond.COUPONPERCENT !== undefined
        ? formatNumber(bond.COUPONPERCENT, 2)
        : '—';
      
      const couponToPrice = calculateCouponToPrice(bond);
      const couponToPriceStr = couponToPrice !== null
        ? formatNumber(couponToPrice, 2)
        : '—';
      
      const regularDuration = calculateRegularDuration(bond);
      const regularDurationStr = regularDuration !== null
        ? formatNumber(regularDuration, 2)
        : '—';
      
      const duration = calculateModifiedDuration(bond);
      const durationStr = duration !== null
        ? formatNumber(duration, 2)
        : '—';
      
      const convexity = formatConvexity(calculateConvexity(bond));
      
      const priceChange = formatPriceChange(calculatePriceChange(bond));

      // Calculate spread (only for fixed coupon bonds without options)
      // Используем дюрацию Маколея вместо срока до погашения для более точного сравнения
      // с доходностью КБД, так как "вес" денежных потоков распределен по всему периоду
      let spreadStr = '—';
      if (isFixedCouponBond(bond)) {
        const horizon = calculateRegularDuration(bond); // Используем дюрацию Маколея вместо срока до погашения
        
        if (horizon !== null && horizon > 0) {
          const zeroCurveYield = interpolateZeroCurveYield(yieldCurveMap, horizon);
          if (zeroCurveYield !== null) {
            const spread = calculateSpread(bond.YIELDATPREVWAPRICE, zeroCurveYield);
            spreadStr = formatSpread(spread);
          }
        }
      }

      // Calculate Z-spread (zero-coupon spread) for fixed coupon bonds without options
      let zSpreadStr = '—';
      if (isFixedCouponBond(bond)) {
        const coupons = couponsData.get(bond.SECID);
        if (coupons && coupons.length > 0) {
          // Use current date as analysis date (only future coupons will be included)
          const currentDate = new Date();
          const zSpread = calculateZSpread(bond, coupons, zerocuponData, currentDate);
          zSpreadStr = formatZSpread(zSpread);
        }
      }
      
      return {
        name: bond.SHORTNAME || '—',
        ticker: bond.SECID || '—',
        maturity: formatMaturity(bond.MATDATE),
        price,
        ytm,
        coupon,
        couponToPrice: couponToPriceStr,
        regularDuration: regularDurationStr,
        duration: durationStr,
        convexity,
        priceChange,
        spread: spreadStr,
        zSpread: zSpreadStr,
        secid: bond.SECID,
      };
    });
  }, [bonds, zerocuponData, couponsData]);

  // Prepare chart data for spread curve with z-spread in basis points
  const chartData = useMemo(() => {
    if (comparisonData.length === 0) return [];

    // Filter and prepare data: only bonds with valid z-spread and duration
    const points = comparisonData
      .filter(row => {
        const duration = parseFloat(row.regularDuration);
        const hasZSpread = row.zSpread && row.zSpread !== '—';
        return hasZSpread && !isNaN(duration) && duration > 0;
      })
      .map(row => {
        // Parse z-spread value (e.g., "+1.23%" or "-1.23%")
        const zSpreadStr = row.zSpread.replace('%', '').replace('+', '').trim();
        const zSpreadPercent = parseFloat(zSpreadStr);
        
        if (isNaN(zSpreadPercent)) {
          return null;
        }

        // Convert z-spread from percentage to basis points (1% = 100 bps)
        const zSpreadBps = zSpreadPercent * 100;
        
        const duration = parseFloat(row.regularDuration);

        return {
          duration,
          zSpreadBps,
          zSpreadPercent,
          ticker: row.ticker,
          name: row.name,
          secid: row.secid,
        };
      })
      .filter((point): point is NonNullable<typeof point> => point !== null)
      .sort((a, b) => a.duration - b.duration); // Sort by duration

    if (points.length === 0) return { points: [], trendLine: [], outliers: [] };

    // Calculate trend line using polynomial regression (degree 2)
    const regressionData = points.map(p => [p.duration, p.zSpreadBps] as [number, number]);
    const result = regression.polynomial(regressionData, { order: 2 });

    // Generate trend line points for visualization
    const minDuration = Math.min(...points.map(p => p.duration));
    const maxDuration = Math.max(...points.map(p => p.duration));
    const step = (maxDuration - minDuration) / 100; // 100 points for smooth curve
    
    const trendLine = [];
    for (let x = minDuration; x <= maxDuration; x += step) {
      const y = result.predict(x)[1];
      trendLine.push({ duration: x, zSpreadBps: y });
    }

    // Calculate outliers (points significantly above or below trend line)
    const OUTLIER_THRESHOLD_BPS = 15; // 15 basis points threshold
    const OUTLIER_THRESHOLD_PERCENT = 0.15; // 15% threshold (alternative)
    
    const outliers = points.map(point => {
      const predictedBps = result.predict(point.duration)[1];
      const residual = point.zSpreadBps - predictedBps;
      const residualPercent = predictedBps !== 0 ? Math.abs(residual / predictedBps) : 0;
      
      // Outlier if residual > 15 bps OR > 15% of predicted value
      const isPositiveOutlier = residual > OUTLIER_THRESHOLD_BPS || 
                                (residualPercent > OUTLIER_THRESHOLD_PERCENT && residual > 0);
      const isNegativeOutlier = residual < -OUTLIER_THRESHOLD_BPS || 
                                (residualPercent > OUTLIER_THRESHOLD_PERCENT && residual < 0);
      
      return {
        ...point,
        predictedBps,
        residual,
        isPositiveOutlier,
        isNegativeOutlier,
        color: isPositiveOutlier ? CHART_CONFIG.COLORS.SUCCESS : // Green for undervalued
               isNegativeOutlier ? CHART_CONFIG.COLORS.ERROR : // Red for overvalued
               CHART_CONFIG.COLORS.PRIMARY, // Blue for normal
      };
    });

    return {
      points: outliers,
      trendLine,
      regression: result,
    };
  }, [comparisonData]);

  // Header components (same as ComparisonTable - simplified version)
  const CustomHeaderWithTooltip = React.memo((params: IHeaderParams) => {
    const displayName = params.displayName || '';
    const tooltipText = params.column?.getColDef().headerTooltip as string | undefined;
    if (!tooltipText) {
      return <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{displayName}</div>;
    }
    return (
      <Tooltip title={tooltipText} arrow placement="top" enterDelay={300} leaveDelay={0} disableInteractive
        slotProps={{ tooltip: { sx: { maxWidth: 400, minWidth: 200, bgcolor: 'rgba(255, 255, 255, 0.98)', color: 'rgba(0, 0, 0, 0.87)', fontSize: '13px', lineHeight: 1.5, padding: '12px 16px', borderRadius: '8px', boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)', border: '1px solid rgba(0, 0, 0, 0.12)' } } }}>
        <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'default' }}>{displayName}</div>
      </Tooltip>
    );
  });
  CustomHeaderWithTooltip.displayName = 'CustomHeaderWithTooltip';

  // Simplified header components (full versions would be same as ComparisonTable)
  const SpreadHeaderWithTooltip = React.memo((_params: IHeaderParams) => (
    <Tooltip title="Премии и отклонения по рынку. Рассчитывается только для облигаций типа «Фикс с известным купоном» без колл или пут опционов на основе кривой бескупонной доходности. Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—»." arrow placement="top" enterDelay={300} leaveDelay={0}
      slotProps={{ tooltip: { sx: { maxWidth: 400, bgcolor: 'rgba(255, 255, 255, 0.98)', color: 'rgba(0, 0, 0, 0.87)', fontSize: '13px', padding: '12px 16px', borderRadius: '8px' } } }}>
      <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', gap: '4px' }}>
        <span>Премии и отклонения по рынку</span>
        <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </div>
    </Tooltip>
  ));
  SpreadHeaderWithTooltip.displayName = 'SpreadHeaderWithTooltip';

  const ZSpreadHeaderWithTooltip = React.memo((_params: IHeaderParams) => (
    <Tooltip title="Спред доходности на основе кривой бескупонной доходности (Z-Spread). Рассчитывается только для облигаций типа «Фикс с известным купоном» без колл или пут опционов. Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—»." arrow placement="top" enterDelay={300} leaveDelay={0}
      slotProps={{ tooltip: { sx: { maxWidth: 500, bgcolor: 'rgba(255, 255, 255, 0.98)', fontSize: '13px', padding: '12px 16px', borderRadius: '8px' } } }}>
      <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', gap: '4px' }}>
        <span>Спред доходности на основе кривой бескупонной доходности</span>
        <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </div>
    </Tooltip>
  ));
  ZSpreadHeaderWithTooltip.displayName = 'ZSpreadHeaderWithTooltip';

  const ModifiedDurationHeaderWithTooltip = React.memo((_params: IHeaderParams) => (
    <Tooltip title="Модифицированная дюрация. Рассчитывается только для облигаций типа «Фикс с известным купоном» без колл или пут опционов. Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—»." arrow placement="top" enterDelay={300} leaveDelay={0}
      slotProps={{ tooltip: { sx: { maxWidth: 500, bgcolor: 'rgba(255, 255, 255, 0.98)', fontSize: '13px', padding: '12px 16px', borderRadius: '8px' } } }}>
      <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', gap: '4px' }}>
        <span>Модифицированная дюрация</span>
        <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </div>
    </Tooltip>
  ));
  ModifiedDurationHeaderWithTooltip.displayName = 'ModifiedDurationHeaderWithTooltip';

  const PriceChangeHeaderWithTooltip = React.memo((_params: IHeaderParams) => (
    <Tooltip title="Изменение цены при изменении ставки на 1%. Рассчитывается только для облигаций типа «Фикс с известным купоном» без колл или пут опционов. Показывает изменение цены при росте ставки (убыток, красный) и при снижении ставки (прибыль, зеленый). Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—»." arrow placement="top" enterDelay={300} leaveDelay={0}
      slotProps={{ tooltip: { sx: { maxWidth: 550, bgcolor: 'rgba(255, 255, 255, 0.98)', fontSize: '13px', padding: '12px 16px', borderRadius: '8px' } } }}>
      <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', gap: '4px' }}>
        <span>Изменение цены при росте / снижении ставки на 1%</span>
        <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </div>
    </Tooltip>
  ));
  PriceChangeHeaderWithTooltip.displayName = 'PriceChangeHeaderWithTooltip';

  const ConvexityHeaderWithTooltip = React.memo((_params: IHeaderParams) => (
    <Tooltip title="Выпуклость. Рассчитывается только для облигаций типа «Фикс с известным купоном» без колл или пут опционов. Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—»." arrow placement="top" enterDelay={300} leaveDelay={0}
      slotProps={{ tooltip: { sx: { maxWidth: 500, bgcolor: 'rgba(255, 255, 255, 0.98)', fontSize: '13px', padding: '12px 16px', borderRadius: '8px' } } }}>
      <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', gap: '4px' }}>
        <span>Выпуклость</span>
        <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </div>
    </Tooltip>
  ));
  ConvexityHeaderWithTooltip.displayName = 'ConvexityHeaderWithTooltip';

  // Cell renderers
  const SpreadCellRenderer = (params: ICellRendererParams<ComparisonRow>) => {
    const spread = params.value || '—';
    const color = getSpreadColor(spread);
    const isNonZero = isSpreadNonZero(spread);
    return (
      <Box sx={{ color, fontWeight: isNonZero ? 600 : 'inherit', width: '100%', textAlign: 'center' }}>{spread}</Box>
    );
  };

  const PriceChangeCellRenderer = (params: ICellRendererParams<ComparisonRow>) => {
    const priceChange = params.value || '—';
    if (priceChange === '—' || !priceChange.includes('/')) {
      return <Box sx={{ width: '100%', textAlign: 'center' }}>{priceChange}</Box>;
    }
    const parts = priceChange.split(' / ');
    if (parts.length !== 2) {
      return <Box sx={{ width: '100%', textAlign: 'center' }}>{priceChange}</Box>;
    }
    return (
      <Box sx={{ width: '100%', textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
        <Box component="span" sx={{ color: '#F44336', fontWeight: 500 }}>{parts[0].trim()}</Box>
        <Box component="span" sx={{ color: 'text.secondary' }}>/</Box>
        <Box component="span" sx={{ color: '#4CAF50', fontWeight: 600 }}>{parts[1].trim()}</Box>
      </Box>
    );
  };

  // Column definitions (same structure as ComparisonTable)
  const columnDefs: ColDef[] = useMemo(() => [
    { field: 'name', headerName: 'Название', minWidth: 120, cellStyle: { textAlign: 'left' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'ticker', headerName: 'Тикер', minWidth: 100, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'maturity', headerName: 'Срок до погашения, лет', minWidth: 120, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'coupon', headerName: 'Доходность купона относительно номинала (%)', minWidth: 160, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'price', headerName: 'Цена (%)', minWidth: 100, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'ytm', headerName: 'Доходность к погашению, YTM (%)', minWidth: 140, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'couponToPrice', headerName: 'Доходность купона к текущей цене (%)', minWidth: 140, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'regularDuration', headerName: 'Дюрация', minWidth: 100, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: CustomHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'duration', headerName: 'Модифицированная дюрация', minWidth: 130, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: ModifiedDurationHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'convexity', headerName: 'Выпуклость', minWidth: 120, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: ConvexityHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'priceChange', headerName: 'Изменение цены при росте / снижении ставки на 1%', minWidth: 240, cellRenderer: PriceChangeCellRenderer, cellStyle: { textAlign: 'center' }, headerClass: 'ag-header-center', headerComponent: PriceChangeHeaderWithTooltip, autoHeaderHeight: true },
    { field: 'spread', headerName: 'Премии и отклонения по рынку', minWidth: 160, cellRenderer: SpreadCellRenderer, cellStyle: { textAlign: 'center' }, headerComponent: SpreadHeaderWithTooltip, headerClass: 'ag-header-center', autoHeaderHeight: true, sortable: false, filter: false },
    { field: 'zSpread', headerName: 'Спред доходности на основе кривой бескупонной доходности', minWidth: 200, cellRenderer: SpreadCellRenderer, cellStyle: { textAlign: 'center' }, headerComponent: ZSpreadHeaderWithTooltip, headerClass: 'ag-header-center', autoHeaderHeight: true, sortable: false, filter: false },
  ] as ColDef[], []);

  const defaultColDef: ColDef = useMemo(() => ({
    sortable: true, filter: true, resizable: true, minWidth: 80, suppressSizeToFit: false, autoHeaderHeight: true,
  }), []);

  const calculateHeaderHeight = useCallback(() => {
    const gridContainer = document.querySelector<HTMLElement>('.ag-theme-material');
    if (!gridContainer) return;
    const headerCells = gridContainer.querySelectorAll<HTMLElement>('.ag-header-cell');
    if (headerCells.length === 0) return;
    let maxContentHeight = 0;
    headerCells.forEach((cell) => {
      const label = cell.querySelector<HTMLElement>('.ag-header-cell-label');
      if (!label) return;
      const originalDisplay = label.style.display;
      const originalHeight = label.style.height;
      label.style.display = 'block';
      label.style.height = 'auto';
      const contentHeight = label.scrollHeight;
      label.style.display = originalDisplay;
      label.style.height = originalHeight;
      if (contentHeight > maxContentHeight) maxContentHeight = contentHeight;
    });
    const calculatedHeight = Math.max(Math.ceil(maxContentHeight) + 24, 60);
    if (calculatedHeight !== headerHeight) {
      setHeaderHeight(calculatedHeight);
      gridContainer.style.setProperty('--ag-header-height', `${calculatedHeight}px`);
      if (gridRef.current?.api) gridRef.current.api.sizeColumnsToFit();
    }
  }, [headerHeight]);

  const onGridReady = useCallback(() => {
    if (gridRef.current?.api) {
      gridRef.current.api.autoSizeAllColumns(false);
      setTimeout(() => calculateHeaderHeight(), 250);
    }
  }, [calculateHeaderHeight]);

  useEffect(() => {
    if (comparisonData.length > 0 && gridRef.current?.api) {
      const timeoutId = setTimeout(() => calculateHeaderHeight(), 500);
      return () => clearTimeout(timeoutId);
    }
  }, [comparisonData.length, columnDefs, calculateHeaderHeight]);

  useEffect(() => {
    const handleResize = () => {
      if (comparisonData.length > 0) {
        setTimeout(() => calculateHeaderHeight(), 100);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [comparisonData.length, calculateHeaderHeight]);

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', width: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: '12px' }}>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
        {/* Emitent Selector */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <FormControl fullWidth>
            <InputLabel>Эмитент</InputLabel>
            <Select
              value={selectedEmitent}
              onChange={(e) => setSelectedEmitent(e.target.value)}
              label="Эмитент"
              disabled={isLoadingEmitents || emitentOptions.length === 0}
            >
              <MenuItem value="">
                <em>Не выбран</em>
              </MenuItem>
              {emitentOptions.map((emitent) => (
                <MenuItem key={emitent} value={emitent}>{emitent}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Tabs Section */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', height: '100%' }}>
          {isLoadingBonds || isLoadingZerocupon || isLoadingCoupons ? (
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
              <LoadingSpinner message={isLoadingBonds ? "Загрузка облигаций..." : isLoadingZerocupon ? "Загрузка данных кривой бескупонной доходности..." : "Загрузка данных о купонах..."} />
            </Box>
          ) : comparisonData.length === 0 ? (
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3, minHeight: 0 }}>
              <Typography variant="body2" color="text.secondary">
                {selectedEmitent ? 'Облигации для выбранного эмитента не найдены' : 'Выберите эмитента для отображения данных'}
              </Typography>
            </Box>
          ) : (
            <>
              {/* Tabs Navigation */}
              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
                  <Tab label="Список облигаций" />
                  <Tab label="График кривой спредов" />
                </Tabs>
              </Box>

              {/* Tab Content */}
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', height: '100%' }}>
                {currentTab === 0 && (
                  <Box sx={{ flex: 1, display: 'flex', px: 2, py: 2, minHeight: 0, overflow: 'hidden', height: '100%' }}>
                    <Box className="ag-theme-material" sx={{ flex: 1, height: '100%', width: '100%', display: 'flex', flexDirection: 'column', ...(headerHeight && { '--ag-header-height': `${headerHeight}px` }),
                      '& .ag-root-wrapper': { border: '1px solid #dee2e6', borderRadius: '4px', height: '100%', display: 'flex', flexDirection: 'column', flex: 1 },
                      '& .ag-body': { flex: 1, minHeight: 0, overflow: 'auto' },
                      '& .ag-body-viewport-wrapper': { flex: 1, minHeight: 0, overflow: 'auto' },
                      '& .ag-body-viewport': { height: '100%' },
                      '& .ag-center-cols-viewport': { height: '100%' },
                      '& .ag-header': { borderBottom: '1px solid #ddd' },
                      '& .ag-header-cell': { display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: '8px 4px', boxSizing: 'border-box', gap: '0px !important', borderRight: '1px solid #dee2e6 !important', borderBottom: '1px solid #dee2e6 !important', fontWeight: 600, color: '#444', background: '#fafafa' },
                      '& .ag-header-cell:last-child': { borderRight: 'none !important' },
                      '& .ag-header-cell-label': { fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: 1.5, flex: '0 1 auto', minWidth: 0, padding: '4px 0px 4px 8px !important', marginRight: '0px !important', marginLeft: '0px !important', marginTop: '0px !important', marginBottom: '0px !important', overflow: 'visible', boxSizing: 'border-box' },
                      '& .ag-header-cell-text': { whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: 1.5, textAlign: 'center', display: 'block', overflow: 'visible', hyphens: 'auto', marginRight: '0px !important', paddingRight: '0px !important' },
                      '& .ag-header-cell-menu-button': { flexShrink: 0, alignSelf: 'center', marginLeft: '1px !important', marginRight: '0px !important', marginTop: '0px !important', marginBottom: '0px !important', padding: '0px !important', width: 'auto !important', minWidth: 'auto !important' },
                      '& .ag-header-cell-filter-button': { flexShrink: 0, alignSelf: 'center', marginLeft: '1px !important', marginRight: '0px !important', marginTop: '0px !important', marginBottom: '0px !important', padding: '0px !important', width: 'auto !important', minWidth: 'auto !important' },
                      '& .ag-header-cell-label + .ag-header-cell-menu-button': { marginLeft: '1px !important' },
                      '& .ag-header-cell-label + .ag-header-cell-filter-button': { marginLeft: '1px !important' },
                      '& .ag-header-cell-filtered .ag-header-cell-menu-button': { opacity: 1 },
                      '& .ag-header-cell-filtered .ag-header-cell-filter-button': { opacity: 1 },
                      '& .ag-cell': { borderRight: '1px solid #dee2e6 !important', borderBottom: '1px solid #dee2e6 !important', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: '1.5 !important', padding: '8px 12px !important', overflow: 'hidden', textOverflow: 'ellipsis', maxHeight: '44px !important', height: '44px !important', boxSizing: 'border-box', '& > *': { maxHeight: '36px !important', overflow: 'hidden' } },
                      '& .ag-row .ag-cell:last-child': { borderRight: 'none !important' },
                      '& .ag-cell[col-id="name"]': { justifyContent: 'flex-start', textAlign: 'left !important' },
                      '& .ag-cell[col-id="ticker"], & .ag-cell[col-id="maturity"], & .ag-cell[col-id="coupon"], & .ag-cell[col-id="price"], & .ag-cell[col-id="ytm"], & .ag-cell[col-id="couponToPrice"], & .ag-cell[col-id="regularDuration"], & .ag-cell[col-id="duration"], & .ag-cell[col-id="convexity"], & .ag-cell[col-id="priceChange"], & .ag-cell[col-id="spread"], & .ag-cell[col-id="zSpread"]': { justifyContent: 'center', textAlign: 'center !important' },
                      '& .ag-row': { cursor: 'default', minHeight: '44px !important', maxHeight: '44px !important', height: '44px !important', '& > *': { maxHeight: '44px !important' } },
                      '& .ag-row-hover': { backgroundColor: '#f7f9fc !important' },
                      '& .ag-header-center .ag-header-cell-label': { justifyContent: 'center' },
                    }}>
                      <AgGridReact<ComparisonRow>
                        ref={gridRef}
                        rowData={comparisonData}
                        columnDefs={columnDefs}
                        defaultColDef={defaultColDef}
                        onGridReady={onGridReady}
                        animateRows={true}
                        pagination={true}
                        paginationPageSize={100}
                        paginationPageSizeSelector={[50, 100, 200, 500]}
                        enableCellTextSelection={true}
                        suppressRowClickSelection={true}
                        headerHeight={headerHeight}
                        rowHeight={44}
                        autoSizeStrategy={{ type: 'fitGridWidth', defaultMinWidth: 80 }}
                        suppressAggFuncInHeader={true}
                        suppressMenuHide={true}
                        getRowId={(params) => params.data.secid}
                        theme="legacy"
                      />
                    </Box>
                  </Box>
                )}

                {currentTab === 1 && (
                  <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 3, minHeight: 0, overflow: 'hidden' }}>
                    {!chartData.points || chartData.points.length === 0 ? (
                      <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography variant="body2" color="text.secondary">
                          Нет данных для построения графика. Выберите эмитента с облигациями типа «Фикс с известным купоном» без опционов, имеющими рассчитанные Z-спреды.
                        </Typography>
                      </Box>
                    ) : (
                      <>
                        <Typography variant="h6" sx={{ mb: 1, flexShrink: 0, fontWeight: 600 }}>
                          Кривая Z-спредов эмитента {selectedEmitent || '—'}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, flexShrink: 0 }}>
                          График показывает зависимость Z-спредов (в базисных пунктах) от срока до погашения. Зеленые точки — потенциально недооцененные облигации (выше линии тренда на 15+ б.п.), красные — переоцененные (ниже линии тренда на 15+ б.п.).
                        </Typography>
                        <Box sx={{ flex: 1, width: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                          <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart
                              margin={{ top: 20, right: 30, left: 80, bottom: 80 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" stroke={CHART_CONFIG.COLORS.GRID} />
                              <XAxis
                                type="number"
                                dataKey="duration"
                                name="Срок до погашения"
                                label={{ value: 'Срок до погашения (лет)', position: 'insideBottom', offset: -10 }}
                                tick={{ fontSize: 12 }}
                                domain={['dataMin - 0.5', 'dataMax + 0.5']}
                              />
                              <YAxis
                                type="number"
                                dataKey="zSpreadBps"
                                name="Z-спред"
                                label={{ value: 'Z-спред (б.п.)', angle: -90, position: 'insideLeft' }}
                                tick={{ fontSize: 12 }}
                                domain={['dataMin - 20', 'dataMax + 20']}
                              />
                              <RechartsTooltip
                                cursor={{ strokeDasharray: '3 3' }}
                                content={({ active, payload }) => {
                                  if (active && payload && payload.length) {
                                    const data = payload[0].payload as typeof chartData.points[0];
                                    return (
                                      <Box
                                        sx={{
                                          backgroundColor: 'white',
                                          border: '1px solid #e0e0e0',
                                          borderRadius: '8px',
                                          padding: '12px',
                                          boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2)',
                                        }}
                                      >
                                        <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                                          {data.name}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          Тикер: {data.ticker}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          Срок до погашения: {data.duration.toFixed(2)} лет
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          Z-Спред: {data.zSpreadBps > 0 ? '+' : ''}{data.zSpreadBps.toFixed(1)} б.п.
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          Прогноз по тренду: {data.predictedBps.toFixed(1)} б.п.
                                        </Typography>
                                        <Typography 
                                          variant="body2" 
                                          color={data.isPositiveOutlier ? CHART_CONFIG.COLORS.SUCCESS : 
                                                 data.isNegativeOutlier ? CHART_CONFIG.COLORS.ERROR : 
                                                 'text.secondary'}
                                          sx={{ fontWeight: data.isPositiveOutlier || data.isNegativeOutlier ? 600 : 'normal' }}
                                        >
                                          Остаток: {data.residual > 0 ? '+' : ''}{data.residual.toFixed(1)} б.п.
                                          {data.isPositiveOutlier && ' (Недооценена)'}
                                          {data.isNegativeOutlier && ' (Переоценена)'}
                                        </Typography>
                                      </Box>
                                    );
                                  }
                                  return null;
                                }}
                              />
                              <Legend />
                              {/* Trend line */}
                              <Line
                                type="monotone"
                                data={chartData.trendLine}
                                dataKey="zSpreadBps"
                                name="Линия тренда"
                                stroke={CHART_CONFIG.COLORS.SECONDARY}
                                strokeWidth={2}
                                dot={false}
                                activeDot={false}
                              />
                              {/* Scatter points with colored outliers */}
                              <Scatter
                                name="Z-спред облигаций"
                                data={chartData.points}
                                fill={CHART_CONFIG.COLORS.PRIMARY}
                              >
                                {chartData.points.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                                <LabelList
                                  dataKey="ticker"
                                  position="right"
                                  offset={5}
                                  style={{ fontSize: 11, fill: '#666' }}
                                />
                              </Scatter>
                            </ScatterChart>
                          </ResponsiveContainer>
                        </Box>
                      </>
                    )}
                  </Box>
                )}
              </Box>
            </>
          )}
        </Box>

      </CardContent>
    </Card>
  );
};
