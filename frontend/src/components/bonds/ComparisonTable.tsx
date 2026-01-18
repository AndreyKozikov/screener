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
  Button,
  Card,
  CardContent,
  Tabs,
  Tab,
  TextField,
  Grid,
  Checkbox,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import SaveIcon from '@mui/icons-material/Save';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useComparisonStore } from '../../stores/comparisonStore';
import { ComparisonImportDialog } from './ComparisonImportDialog';
import { formatNumber, calculateCouponFrequency } from '../../utils/formatters';
import { fetchZerocuponData, type ZerocuponRecord } from '../../api/zerocupon';
import {
  getLatestZerocuponRecord,
  buildYieldCurveMap,
  interpolateZeroCurveYield,
  calculateSpread,
  formatSpread,
} from '../../utils/zerocuponInterpolation';
import { calculateGSpread, formatGSpread, calculateZSpread } from '../../utils/SpreadCalculation';
import { fetchBondCoupons } from '../../api/bonds';
import type { Coupon } from '../../types/coupon';
import dayjs from 'dayjs';
import type { BondListItem } from '../../types/bond';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { fetchForecastData, type ForecastData } from '../../api/forecast';

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
  gSpread: string;
  zSpread: string;
  secid: string;
}

interface TotalReturnResult {
  secid: string;
  name: string;
  ticker: string;
  // Input parameters
  investAmount: number;
  cleanPricePercent: number;
  nominal: number;
  accruedInterest: number;
  couponRate: number;
  years: number;
  modDuration: number | null;
  targetYieldChange: number;
  // Intermediate calculations
  priceRub: number;
  dirtyPriceRub: number;
  quantity: number;
  cashBalance: number;
  totalCoupons: number;
  grossCouponsReceived: number;
  priceChangePercent: number;
  futureCleanPricePercent: number;
  saleProceeds: number;
  // Final results
  finalBalance: number;
  absoluteProfit: number;
  totalReturnPercent: number;
  annualReturn: number;
}

/**
 * ComparisonTable Component
 * 
 * Displays comparison table for selected bonds using AG Grid
 */
export const ComparisonTable: React.FC = () => {
  const { comparisonBonds, removeBondFromComparison, loadBondsToComparison, clearComparison } = useComparisonStore();
  const [zerocuponData, setZerocuponData] = useState<ZerocuponRecord[]>([]);
  const [isLoadingZerocupon, setIsLoadingZerocupon] = useState(false);
  const [couponsData, setCouponsData] = useState<Map<string, Coupon[]>>(new Map());
  const [isLoadingCoupons, setIsLoadingCoupons] = useState(false);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const gridRef = useRef<AgGridReact<ComparisonRow>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);
  const [currentTab, setCurrentTab] = useState(0);
  
  // Cash flow calculation state
  const [investAmount, setInvestAmount] = useState<number>(10000);
  const [years, setYears] = useState<number>(3);
  const [forecastRate, setForecastRate] = useState<number | null>(null);
  const [currentRate, setCurrentRate] = useState<number | null>(null);
  const [_forecastData, setForecastData] = useState<ForecastData | null>(null);
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);
  const [useForecastRate, setUseForecastRate] = useState<boolean>(false);
  const [useManualParams, setUseManualParams] = useState<boolean>(false);
  // Manual price and accrued interest values per bond (keyed by secid)
  const [manualPrices, setManualPrices] = useState<Map<string, { cleanPricePercent: number; accruedInterest: number }>>(new Map());
  const [isParamsDialogOpen, setIsParamsDialogOpen] = useState<boolean>(false);

  // Load zero-coupon yield curve data when component mounts or bonds change
  useEffect(() => {
    if (comparisonBonds.length === 0) return;

    const loadZerocuponData = async () => {
      try {
        setIsLoadingZerocupon(true);
        // Load data for the last year to get the latest curve
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
  }, [comparisonBonds.length]);

  // Load coupons data for fixed coupon bonds
  useEffect(() => {
    if (comparisonBonds.length === 0) return;

    const loadCouponsData = async () => {
      try {
        setIsLoadingCoupons(true);
        const couponsMap = new Map<string, Coupon[]>();

        // Load coupons only for fixed coupon bonds
        const fixedCouponBonds = comparisonBonds.filter(
          bond => bond.BONDTYPE43 === 'Фикс с известным купоном'
        );

        // Load coupons in parallel
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
  }, [comparisonBonds]);

  // Load forecast data for rate prediction (only if checkbox is checked)
  useEffect(() => {
    if (!useForecastRate) {
      // If checkbox is unchecked, clear forecast data and rate
      setForecastData(null);
      setForecastRate(null);
      setIsLoadingForecast(false);
      return;
    }

    const loadForecast = async () => {
      try {
        setIsLoadingForecast(true);
        const data = await fetchForecastData();
        setForecastData(data);
        
        // Auto-fill forecast rate based on current year + years horizon
        const currentYear = new Date().getFullYear();
        const targetYear = currentYear + years;
        
        if (data && data.data.основные_показатели) {
          // Find key rate field name - search in names mapping
          const keyRateFieldName = Object.keys(data.names.основные_показатели).find(
            key => {
              const name = data.names.основные_показатели[key]?.toLowerCase() || '';
              return name.includes('ключевая ставка') || 
                     name.includes('ключевая ставка банка россии') ||
                     name.includes('ставка банка россии');
            }
          );
          
          if (keyRateFieldName) {
            const yearData = data.data.основные_показатели.find(ind => ind.год === targetYear);
            if (yearData && keyRateFieldName in yearData) {
              const value = yearData[keyRateFieldName];
              if (value !== null && value !== undefined) {
                if (typeof value === 'object' && 'мин' in value && 'макс' in value) {
                  const val = value as { мин: number; макс: number };
                  const avgRate = (val.мин + val.макс) / 2;
                  setForecastRate(avgRate);
                } else if (typeof value === 'number') {
                  setForecastRate(value);
                }
              }
            }
          }
        }
      } catch (error) {
        console.error('Error loading forecast data:', error);
      } finally {
        setIsLoadingForecast(false);
      }
    };

    void loadForecast();
  }, [years, useForecastRate]);

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

  // Format maturity date as years to maturity
  const formatMaturity = (matDate: string | null): string => {
    if (!matDate) return '—';
    
    try {
      const yearsToMaturity = calculateYearsToMaturity(matDate);
      
      if (yearsToMaturity === null) {
        return '—';
      }
      
      // Round to 1 decimal place and return only years
      const roundedYears = Math.round(yearsToMaturity * 10) / 10;
      return roundedYears.toFixed(1);
    } catch {
      return '—';
    }
  };

  // Check if modified duration is applicable for this bond
  // Modified duration is only applicable for:
  // 1. Fixed coupon bonds with known coupon rate (BONDTYPE43 === "Фикс с известным купоном")
  // 2. Bonds without embedded options (no call or put options)
  const isModifiedDurationApplicable = (bond: BondListItem): boolean => {
    // Check if bond type is "Фикс с известным купоном"
    if (bond.BONDTYPE43 !== 'Фикс с известным купоном') {
      return false;
    }
    
    // Check if bond has call or put options (embedded options)
    // If either CALLOPTIONDATE or PUTOPTIONDATE is not null, bond has embedded options
    if (bond.CALLOPTIONDATE !== null && bond.CALLOPTIONDATE !== undefined) {
      return false;
    }
    
    if (bond.PUTOPTIONDATE !== null && bond.PUTOPTIONDATE !== undefined) {
      return false;
    }
    
    return true;
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
  // Modified Duration is only applicable for fixed coupon bonds without embedded options
  // According to financial theory, modified duration directly estimates percentage price change
  // per 100 basis points change in yield, but only for bonds without embedded options
  const calculateModifiedDuration = (bond: BondListItem): number | null => {
    // Check if modified duration is applicable for this bond type
    if (!isModifiedDurationApplicable(bond)) {
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
  // Only applicable for fixed coupon bonds without embedded options
  const calculateConvexity = (bond: BondListItem): number | null => {
    // Check if convexity is applicable for this bond type
    if (!isModifiedDurationApplicable(bond)) {
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
  // This calculation is only valid for bonds where modified duration is applicable
  // (fixed coupon bonds without embedded options)
  const calculatePriceChange = (bond: BondListItem): { upShock: number; downShock: number } | null => {
    // Check if modified duration is applicable for this bond type
    if (!isModifiedDurationApplicable(bond)) {
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
    if (comparisonBonds.length === 0) return [];

    // Get latest zero-coupon yield curve record
    const latestRecord = getLatestZerocuponRecord(zerocuponData);
    if (!latestRecord) {
      // If no zerocupon data, return data without spread
      return comparisonBonds.map((bond) => {
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
          gSpread: '—',
          zSpread: '—',
          secid: bond.SECID,
        };
      });
    }

    // Build yield curve map
    const yieldCurveMap = buildYieldCurveMap(latestRecord);

    return comparisonBonds.map((bond) => {
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

      // Calculate spread (only for fixed coupon bonds)
      // Используем дюрацию Маколея вместо срока до погашения для более точного сравнения
      // с доходностью КБД, так как "вес" денежных потоков распределен по всему периоду
      let spreadStr = '—';
      if (bond.BONDTYPE43 === 'Фикс с известным купоном') {
        const horizon = calculateRegularDuration(bond); // Используем дюрацию Маколея вместо срока до погашения
        
        if (horizon !== null && horizon > 0) {
          const zeroCurveYield = interpolateZeroCurveYield(yieldCurveMap, horizon);
          if (zeroCurveYield !== null) {
            const spread = calculateSpread(bond.YIELDATPREVWAPRICE, zeroCurveYield);
            spreadStr = formatSpread(spread);
          }
        }
      }

      // Calculate G-spread for fixed coupon bonds
      // G-spread = Actual YTM - Theoretical YTM (where Theoretical YTM is derived from KBD)
      let gSpreadStr = '—';
      if (bond.BONDTYPE43 === 'Фикс с известным купоном') {
        const coupons = couponsData.get(bond.SECID);
        if (coupons && coupons.length > 0) {
          // Use current date as analysis date (only future coupons will be included)
          const currentDate = new Date();
          const gSpread = calculateGSpread(bond, coupons, zerocuponData, currentDate);
          gSpreadStr = formatGSpread(gSpread);
        }
      }

      // Calculate Z-spread for fixed coupon bonds without embedded options
      // Z-spread is calculated only for bonds that meet the criteria
      let zSpreadStr = '—';
      if (isModifiedDurationApplicable(bond)) {
        const coupons = couponsData.get(bond.SECID);
        if (coupons && coupons.length > 0) {
          // Use current date as analysis date (only future coupons will be included)
          const currentDate = new Date();
          const zSpread = calculateZSpread(bond, coupons, zerocuponData, currentDate);
          zSpreadStr = formatGSpread(zSpread); // Use same formatting function as G-spread
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
        gSpread: gSpreadStr,
        zSpread: zSpreadStr,
        secid: bond.SECID,
      };
    });
  }, [comparisonBonds, zerocuponData, couponsData]);

  // Custom header component with Material-UI Tooltip (same as PortfolioTable)
  const CustomHeaderWithTooltip = React.memo((params: IHeaderParams) => {
    const displayName = params.displayName || '';
    const tooltipText = params.column?.getColDef().headerTooltip as string | undefined;
    
    if (!tooltipText) {
      return (
        <div className="ag-header-cell-label" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {displayName}
        </div>
      );
    }

    return (
      <Tooltip
        title={tooltipText}
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        disableInteractive
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 400,
              minWidth: 200,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
              fontFamily: 'Roboto, Helvetica, Arial, sans-serif',
              fontWeight: 400,
              wordWrap: 'break-word',
              whiteSpace: 'normal',
              textAlign: 'left',
              '& .MuiTooltip-arrow': {
                color: 'rgba(255, 255, 255, 0.98)',
                '&::before': {
                  border: '1px solid rgba(0, 0, 0, 0.12)',
                },
              },
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'default'
          }}
        >
          {displayName}
        </div>
      </Tooltip>
    );
  });

  CustomHeaderWithTooltip.displayName = 'CustomHeaderWithTooltip';

  // Custom header component with tooltip for spread column (with special content)
  const SpreadHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              Показывает отклонение доходности облигации от расчетной рыночной доходности сопоставимых выпусков (по дюрации Маколея и кредитному качеству). Использование дюрации вместо срока до погашения обеспечивает более точное сравнение, так как учитывает распределение "веса" денежных потоков по всему периоду.
            </Typography>
            <Typography variant="body2">
              <strong>Положительное значение</strong> — облигация предлагает доходность выше рыночной нормы: рынок закладывает дополнительную премию, выпуск выглядит относительно недооценённым.
            </Typography>
            <Typography variant="body2">
              <strong>Отрицательное значение</strong> — доходность ниже рыночной нормы: премия отсутствует, выпуск выглядит относительно переоценённым.
            </Typography>
            <Typography variant="body2">
              Используется для оценки относительной привлекательности облигации при сопоставимом риске.
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 400,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>Премии и отклонения по рынку</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  SpreadHeaderWithTooltip.displayName = 'SpreadHeaderWithTooltip';

  // Custom header component with tooltip for G-spread column (with special content)
  const GSpreadHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              <strong>G-спред (Government Spread)</strong> — разница между фактической доходностью к погашению (YTM) облигации и теоретической доходностью, рассчитанной на основе кривой бескупонной доходности (КБД).
            </Typography>
            <Typography variant="body2">
              <strong>Формула:</strong> G-спред = YTM_фактическая - YTM_теоретическая
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Как это считается:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              1. Все будущие купоны и номинал облигации дисконтируются по спот-ставкам из кривой бескупонной доходности (КБД) для соответствующих сроков.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              2. Из полученной теоретической цены вычисляется теоретическая YTM.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              3. G-спред = Фактическая YTM (рыночная) - Теоретическая YTM (из КБД).
            </Typography>
            <Typography variant="body2" sx={{ pl: 2, mt: 0.5 }}>
              Положительное значение означает премию за кредитный риск и риск ликвидности. Отрицательное — дисконт (облигация торгуется дешевле теоретической цены).
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>🔍 Как интерпретировать значение</strong>
            </Typography>
            <Typography variant="body2">
              <strong>Положительное значение</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Облигация даёт доходность выше рыночной нормы.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Возможна недооценка, инвестор получает дополнительную премию.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Отрицательное значение</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Облигация торгуется дороже рынка.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Обычно это надёжные или высоколиквидные бумаги.
            </Typography>
            <Typography variant="body2">
              <strong>Около нуля</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Цена близка к справедливой рыночной оценке.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>✅ Как выбирать облигации</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Сравнивайте облигации одного типа (сектор, надёжность, срок).
            </Typography>
            <Typography variant="body2">
              <strong>При прочих равных:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • чем выше спред — тем лучше;
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • одинаковый спред при большем сроке — предпочтительнее.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Очень высокий спред может означать повышенный риск — его нужно проверять.
            </Typography>
            <Typography variant="body2">
              <strong>Практическое правило:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Предпочтение стоит отдавать облигациям с устойчивым положительным спредом по сравнению с аналогами.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(0, 0, 0, 0.12)' }}>
              <strong>⚠️ Важно:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              В то время как «Премия по рынку» оценивает выгоду облигации «на глазок» только по дате её финала (используя дюрацию), G-спред проводит детальную проверку каждой купонной выплаты через кривую бескупонной доходности, показывая точную разницу между рыночной и теоретической доходностью. G-спред отличается от Z-спреда: Z-спред — это постоянная надбавка, которую нужно добавить ко всем спот-ставкам КБД, чтобы теоретическая цена равнялась рыночной цене.
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 500,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
              '& .MuiTypography-root': {
                color: 'rgba(0, 0, 0, 0.87) !important',
              },
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>G-спред (на основе кривой бескупонной доходности)</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  GSpreadHeaderWithTooltip.displayName = 'GSpreadHeaderWithTooltip';

  // Custom header component with tooltip for Z-spread column (with special content)
  const ZSpreadHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              <strong>Z-спред (Zero-Volatility Spread)</strong> — постоянная надбавка (в процентных пунктах), которую необходимо добавить ко всем спот-ставкам кривой бескупонной доходности (КБД), чтобы теоретическая цена облигации равнялась её текущей рыночной цене.
            </Typography>
            <Typography variant="body2">
              <strong>Формула:</strong> Рыночная_Грязная_Цена = Σ(Будущий_Платеж / (1 + (Спот_Ставка + Z) / Частота_Выплат) ^ (Время_в_годах * Частота_Выплат))
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Как это считается:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              1. Для каждого будущего купонного платежа берется соответствующая спот-ставка из КБД (с интерполяцией при необходимости).
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              2. К каждой спот-ставке добавляется одна и та же константа Z (Z-spread).
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              3. Методом бисекции находится такое значение Z, при котором сумма дисконтированных платежей равна рыночной грязной цене (чистая цена + НКД).
            </Typography>
            <Typography variant="body2" sx={{ pl: 2, mt: 0.5 }}>
              Z-спред считается более точным показателем премии за риск, чем G-спред, потому что учитывает всю форму кривой доходности и структуру купонных выплат, что позволяет более точно сопоставлять облигации с различными сроками и купонными структурами.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>🔍 Как интерпретировать значение</strong>
            </Typography>
            <Typography variant="body2">
              <strong>Положительное значение</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Облигация требует дополнительной премии за риск и неликвидность сверх безрисковой ставки. Чем выше Z-спред, тем больше риск или требуемая инвесторами компенсация.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Отрицательное значение</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Облигация торгуется дороже, чем должна стоить по безрисковой кривой. Обычно это очень надежные или высоколиквидные бумаги.
            </Typography>
            <Typography variant="body2">
              <strong>Около нуля</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Облигация справедливо оценена рынком относительно безрисковой кривой доходности.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(0, 0, 0, 0.12)' }}>
              <strong>⚠️ Важно:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Z-спред рассчитывается только для облигаций типа «Фикс с известным купоном» без встроенных опционов (колл или пут). Для облигаций с опционами и остальных видов облигаций значение не рассчитывается и отображается как «—». Z-спред отличается от G-спреда: G-спред — это разница между фактической и теоретической YTM, а Z-спред — это константа, добавляемая ко всем спот-ставкам для точного совпадения цен.
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 550,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
              '& .MuiTypography-root': {
                color: 'rgba(0, 0, 0, 0.87) !important',
              },
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>Z-спред (Zero-Volatility Spread)</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  ZSpreadHeaderWithTooltip.displayName = 'ZSpreadHeaderWithTooltip';

  // Custom header component with tooltip for modified duration column (with special content)
  const ModifiedDurationHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              Показывает, насколько изменится цена облигации при изменении рыночной ставки.
            </Typography>
            <Typography variant="body2">
              <strong>Проще:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              если ставки вырастут или снизятся на 1%, цена облигации изменится примерно на значение дюрации в процентах.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>🔍 Как интерпретировать</strong>
            </Typography>
            <Typography variant="body2">
              <strong>Дюрация 1,5</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              → при изменении ставки на 1% цена изменится примерно на 1,5%.
            </Typography>
            <Typography variant="body2">
              <strong>Чем выше дюрация, тем:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • сильнее колеблется цена;
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • выше процентный риск.
            </Typography>
            <Typography variant="body2">
              <strong>Чем ниже дюрация, тем:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • стабильнее цена;
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • ниже чувствительность к ставкам.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>✅ Как использовать</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • Для консервативных инвестиций выбирают облигации с низкой дюрацией.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • Для поиска повышенной доходности допустима более высокая дюрация.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • При сравнении облигаций одинаковый спред при меньшей дюрации — предпочтительнее.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Важно:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Модифицированная дюрация учитывает только изменение ставок и не отражает кредитный риск эмитента.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(0, 0, 0, 0.12)' }}>
              Модифицированная дюрация рассчитывается только для облигаций с фиксированным купоном (тип "Фикс с известным купоном") без встроенных опционов (колл и пут опционов). Для других типов облигаций значение не рассчитывается и отображается как "—".
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 500,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>Модифицированная дюрация</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  ModifiedDurationHeaderWithTooltip.displayName = 'ModifiedDurationHeaderWithTooltip';

  // Custom header component with tooltip for price change column (with special content)
  const PriceChangeHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              <strong>О чем говорит этот показатель?</strong> Этот столбец моделирует «стресс-тест» для вашей облигации. Он показывает, как изменится рыночная цена бумаги, если Центральный Банк или рынок изменят процентные ставки ровно на 1% (100 базисных пунктов) в ту или иную сторону.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>В чем секрет «двойного» значения (Эффект выпуклости):</strong> Если бы мы использовали только обычную дюрацию, цена при росте ставки падала бы ровно на столько же, на сколько росла бы при ее падении (например, -5.00% / +5.00%). Но реальные облигации ведут себя иначе — их график цены напоминает дугу, а не прямую линию.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              Этот эффект называется выпуклостью (Convexity). Он создает полезную для инвестора асимметрию:
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>При росте ставок (Первое число):</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Выпуклость работает как «подушка безопасности». Она замедляет падение цены, делая ваш убыток меньше, чем предсказывает простая математика дюрации.
            </Typography>
            <Typography variant="body2">
              <strong>При падении ставок (Второе число):</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Выпуклость работает как «ускоритель». Она подталкивает цену вверх сильнее, позволяя вам заработать больше.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>✅ Как анализировать эти данные при выборе облигаций:</strong>
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>🔍 Сравните разницу:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Посмотрите на разрыв между падением и ростом. Например, если у одной облигации прогноз -4.90% / +5.10%, а у другой -4.70% / +5.30%, то вторая облигация лучше. Она более «гибкая»: меньше теряет в плохие времена и больше приносит в хорошие.
            </Typography>
            <Typography variant="body2">
              <strong>⚠️ Оценивайте риск:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Первое число (отрицательное) — это ваш риск «здесь и сейчас». Если вы ждете повышения ставки ЦБ, выбирайте бумаги, где это число минимально.
            </Typography>
            <Typography variant="body2">
              <strong>💰 Ищите «бонус»:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Разница между этими числами — это ваша бесплатная страховка. Чем выше выпуклость облигации, тем больше этот «бонус» за лояльность к риску.
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 550,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>Изменение цены при росте / снижении ставки на 1%</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  PriceChangeHeaderWithTooltip.displayName = 'PriceChangeHeaderWithTooltip';

  // Custom header component with tooltip for convexity column (with special content)
  const ConvexityHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    return (
      <Tooltip
        title={
          <Box sx={{ p: 0.5 }}>
            <Typography variant="body2">
              Выпуклость (Convexity) измеряет нелинейность изменения цены облигации при изменении доходности.
            </Typography>
            <Typography variant="body2">
              <strong>Проще:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Выпуклость показывает, насколько точна оценка изменения цены, рассчитанная с помощью модифицированной дюрации.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>🔍 Как интерпретировать</strong>
            </Typography>
            <Typography variant="body2">
              <strong>Положительная выпуклость</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              При снижении ставок цена растет больше, чем предсказывает дюрация. При росте ставок цена падает меньше, чем предсказывает дюрация. Это выгодно для инвестора.
            </Typography>
            <Typography variant="body2">
              <strong>Чем выше выпуклость, тем:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • больше "защита" от роста ставок (цена падает медленнее);
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • больше выгода от снижения ставок (цена растет быстрее).
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>✅ Как использовать</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • При сравнении облигаций с одинаковой дюрацией, выше выпуклость — лучше.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • Выпуклость особенно важна при высокой волатильности процентных ставок.
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              • Выпуклость учитывается вместе с модифицированной дюрацией для более точной оценки риска.
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <strong>Важно:</strong>
            </Typography>
            <Typography variant="body2" sx={{ pl: 2 }}>
              Выпуклость рассчитывается только для облигаций с фиксированным купоном (тип "Фикс с известным купоном") без встроенных опционов. Для других типов облигаций значение не рассчитывается и отображается как "—".
            </Typography>
          </Box>
        }
        arrow
        placement="top"
        enterDelay={300}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              maxWidth: 500,
              bgcolor: 'rgba(255, 255, 255, 0.98)',
              color: 'rgba(0, 0, 0, 0.87)',
              fontSize: '13px',
              lineHeight: 1.5,
              padding: '12px 16px',
              borderRadius: '8px',
              boxShadow: '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12)',
              border: '1px solid rgba(0, 0, 0, 0.12)',
            },
          },
        }}
      >
        <div 
          className="ag-header-cell-label" 
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            cursor: 'help',
            gap: '4px',
          }}
        >
          <span>Выпуклость</span>
          <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        </div>
      </Tooltip>
    );
  });

  ConvexityHeaderWithTooltip.displayName = 'ConvexityHeaderWithTooltip';

  // Column definitions for AG Grid
  const columnDefs: ColDef[] = useMemo(() => {
    // Remove bond renderer
    const RemoveBondRenderer = (params: ICellRendererParams<ComparisonRow>) => {
      const row = params.data;
      if (!row) return null;

      const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        removeBondFromComparison(row.secid);
      };

      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            cursor: 'default',
          }}
        >
          <Box
            component="button"
            onClick={handleClick}
            sx={{
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'error.main',
              '&:hover': {
                backgroundColor: 'error.light',
                borderRadius: '4px',
              },
            }}
          >
            <DeleteIcon fontSize="small" />
          </Box>
        </Box>
      );
    };

    // Spread cell renderer with color
    const SpreadCellRenderer = (params: ICellRendererParams<ComparisonRow>) => {
      const spread = params.value || '—';
      const color = getSpreadColor(spread);
      const isNonZero = isSpreadNonZero(spread);
      
      return (
        <Box
          sx={{
            color,
            fontWeight: isNonZero ? 600 : 'inherit',
            width: '100%',
            textAlign: 'center',
          }}
        >
          {spread}
        </Box>
      );
    };

    // Price change cell renderer with color highlighting
    // First number (loss when rates increase) - pale red, second number (gain when rates decrease) - bright green
    const PriceChangeCellRenderer = (params: ICellRendererParams<ComparisonRow>) => {
      const priceChange = params.value || '—';
      
      if (priceChange === '—' || !priceChange.includes('/')) {
        return (
          <Box
            sx={{
              width: '100%',
              textAlign: 'center',
            }}
          >
            {priceChange}
          </Box>
        );
      }
      
      // Parse the string format: "-X.XX% / +Y.YY%"
      const parts = priceChange.split(' / ');
      if (parts.length !== 2) {
        return (
          <Box
            sx={{
              width: '100%',
              textAlign: 'center',
            }}
          >
            {priceChange}
          </Box>
        );
      }
      
      const firstPart = parts[0].trim(); // Loss (negative) - pale red
      const secondPart = parts[1].trim(); // Gain (positive) - bright green
      
      return (
        <Box
          sx={{
            width: '100%',
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
          }}
        >
          <Box
            component="span"
            sx={{
              color: '#F44336', // Bright red (ярко-красный)
              fontWeight: 500,
            }}
          >
            {firstPart}
          </Box>
          <Box
            component="span"
            sx={{
              color: 'text.secondary',
            }}
          >
            /
          </Box>
          <Box
            component="span"
            sx={{
              color: '#4CAF50', // Bright green (ярко-зеленый)
              fontWeight: 600,
            }}
          >
            {secondPart}
          </Box>
        </Box>
      );
    };

    return [
      {
        field: 'name',
        headerName: 'Название',
        minWidth: 120,
        cellStyle: { textAlign: 'left' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'ticker',
        headerName: 'Тикер',
        minWidth: 100,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'maturity',
        headerName: 'Срок до погашения, лет',
        minWidth: 120,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'coupon',
        headerName: 'Доходность купона относительно номинала (%)',
        minWidth: 160,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'price',
        headerName: 'Цена (%)',
        minWidth: 100,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'ytm',
        headerName: 'Доходность к погашению, YTM (%)',
        minWidth: 140,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'couponToPrice',
        headerName: 'Доходность купона к текущей цене (%)',
        minWidth: 140,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'regularDuration',
        headerName: 'Дюрация',
        minWidth: 100,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'duration',
        headerName: 'Модифицированная дюрация',
        minWidth: 130,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: ModifiedDurationHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'convexity',
        headerName: 'Выпуклость',
        minWidth: 120,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: ConvexityHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'priceChange',
        headerName: 'Изменение цены при росте / снижении ставки на 1%',
        minWidth: 240,
        cellRenderer: PriceChangeCellRenderer,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: PriceChangeHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'spread',
        headerName: 'Премии и отклонения по рынку',
        minWidth: 160,
        cellRenderer: SpreadCellRenderer,
        cellStyle: { textAlign: 'center' },
        headerComponent: SpreadHeaderWithTooltip,
        headerClass: 'ag-header-center',
        autoHeaderHeight: true,
        sortable: false,
        filter: false,
      },
      {
        field: 'gSpread',
        headerName: 'G-спред (на основе кривой бескупонной доходности)',
        minWidth: 200,
        cellRenderer: SpreadCellRenderer,
        cellStyle: { textAlign: 'center' },
        headerComponent: GSpreadHeaderWithTooltip,
        headerClass: 'ag-header-center',
        autoHeaderHeight: true,
        sortable: false,
        filter: false,
      },
      {
        field: 'zSpread',
        headerName: 'Z-спред (Zero-Volatility Spread)',
        minWidth: 200,
        cellRenderer: SpreadCellRenderer,
        cellStyle: { textAlign: 'center' },
        headerComponent: ZSpreadHeaderWithTooltip,
        headerClass: 'ag-header-center',
        autoHeaderHeight: true,
        sortable: false,
        filter: false,
      },
      {
        field: 'actions',
        headerName: 'Действия',
        minWidth: 120,
        width: 120,
        pinned: 'right',
        sortable: false,
        filter: false,
        suppressMenu: true,
        resizable: false,
        cellRenderer: RemoveBondRenderer,
        cellStyle: { textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
        suppressSizeToFit: true,
      },
    ] as ColDef[];
  }, [removeBondFromComparison]);

  // Default column properties
  const defaultColDef: ColDef = useMemo(() => ({
    sortable: true,
    filter: true,
    resizable: true,
    minWidth: 80,
    suppressSizeToFit: false,
    autoHeaderHeight: true,
  }), []);

  // Calculate dynamic header height
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
      const originalOverflow = label.style.overflow;
      
      label.style.display = 'block';
      label.style.height = 'auto';
      label.style.overflow = 'visible';

      const contentHeight = label.scrollHeight;
      
      label.style.display = originalDisplay;
      label.style.height = originalHeight;
      label.style.overflow = originalOverflow;

      if (contentHeight > maxContentHeight) {
        maxContentHeight = contentHeight;
      }
    });

    const calculatedHeight = Math.max(Math.ceil(maxContentHeight) + 24, 60);

    if (calculatedHeight !== headerHeight) {
      setHeaderHeight(calculatedHeight);
      
      gridContainer.style.setProperty('--ag-header-height', `${calculatedHeight}px`);
      
      if (gridRef.current?.api) {
        gridRef.current.api.sizeColumnsToFit();
      }
    }
  }, [headerHeight]);

  // Handle grid ready
  const onGridReady = useCallback(() => {
    if (gridRef.current?.api) {
      gridRef.current.api.autoSizeAllColumns(false);
      
      setTimeout(() => {
        calculateHeaderHeight();
      }, 250);
    }
  }, [calculateHeaderHeight]);

  // Recalculate header height when data changes
  useEffect(() => {
    if (comparisonData.length > 0 && gridRef.current?.api) {
      const timeoutId = setTimeout(() => {
        calculateHeaderHeight();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [comparisonData.length, columnDefs, calculateHeaderHeight]);

  // Recalculate on window resize
  useEffect(() => {
    const handleResize = () => {
      if (comparisonData.length > 0) {
        setTimeout(() => {
          calculateHeaderHeight();
        }, 100);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [comparisonData.length, calculateHeaderHeight]);

  // Generate markdown table
  const generateMarkdown = (): string => {
    const headers = [
      'Название',
      'Тикер',
      'Срок до погашения, лет',
      'Доходность купона относительно номинала (%)',
      'Цена (%)',
      'Доходность к погашению, YTM (%)',
      'Доходность купона к текущей цене (%)',
      'Дюрация',
      'Модифицированная дюрация',
      'Выпуклость',
      'Изменение цены при росте / снижении ставки на 1%',
      'Премии и отклонения по рынку',
      'G-спред (на основе кривой бескупонной доходности)',
      'Z-спред (Zero-Volatility Spread)',
    ];
    
    // Calculate column widths for alignment
    const colWidths = headers.map((header, colIndex) => {
      let maxWidth = header.length;
      comparisonData.forEach((row) => {
        const values = [
          row.name,
          row.ticker,
          row.maturity,
          row.coupon,
          row.price,
          row.ytm,
          row.couponToPrice,
          row.regularDuration,
          row.duration,
          row.convexity,
          row.priceChange,
          row.spread,
          row.gSpread,
          row.zSpread,
        ];
        const cellValue = values[colIndex] || '';
        if (cellValue.length > maxWidth) {
          maxWidth = cellValue.length;
        }
      });
      return Math.max(maxWidth, 3); // Minimum width of 3 for separator
    });
    
    // Create header row
    const headerRow = '| ' + headers
      .map((header, i) => header.padEnd(colWidths[i]))
      .join(' | ') + ' |';
    
    // Create separator row
    const separatorRow = '| ' + colWidths.map((width) => '-'.repeat(width)).join(' | ') + ' |';
    
    // Create data rows
    const dataRows = comparisonData.map((row) => {
      const values = [
        row.name,
        row.ticker,
        row.maturity,
        row.coupon, // Доходность купона относительно номинала (%)
        row.price, // Цена (%)
        row.ytm, // Доходность к погашению, YTM (%)
        row.couponToPrice, // Доходность купона к текущей цене (%)
        row.regularDuration, // Дюрация
        row.duration, // Модифицированная дюрация
        row.convexity, // Выпуклость
        row.priceChange, // Изменение цены при росте / снижении ставки на 1%
        row.spread, // Премии и отклонения по рынку
        row.gSpread, // G-спред (на основе кривой бескупонной доходности) = YTM_фактическая - YTM_теоретическая
        row.zSpread, // Z-спред (Zero-Volatility Spread) = постоянная надбавка к спот-ставкам КБД для совпадения цен
      ];
      return '| ' + values
        .map((value, i) => (value || '—').padEnd(colWidths[i]))
        .join(' | ') + ' |';
    });
    
    return [headerRow, separatorRow, ...dataRows].join('\n');
  };

  // Handle download markdown
  const handleDownloadMarkdown = () => {
    const markdown = generateMarkdown();
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `comparison_analysis_${new Date().toISOString().split('T')[0]}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Escape CSV value (handle quotes, semicolons, newlines)
  const escapeCsvValue = (value: string | number | null | undefined): string => {
    if (value === null || value === undefined) {
      return '';
    }
    
    const str = String(value);
    
    // If value contains semicolon, quote, or newline, wrap in quotes and escape quotes
    if (str.includes(';') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    
    return str;
  };

  // Handle export to CSV
  const handleExportToCsv = () => {
    if (comparisonData.length === 0) {
      return;
    }

    // CSV headers matching the column order in the table
    const headers = [
      'Название',
      'Тикер',
      'Срок до погашения, лет',
      'Доходность купона относительно номинала (%)',
      'Цена (%)',
      'Доходность к погашению, YTM (%)',
      'Доходность купона к текущей цене (%)',
      'Дюрация',
      'Модифицированная дюрация',
      'Выпуклость',
      'Изменение цены при росте / снижении ставки на 1%',
      'Премии и отклонения по рынку',
      'G-спред (на основе кривой бескупонной доходности)',
      'Z-спред (Zero-Volatility Spread)',
    ];

    // Create CSV rows
    const csvRows = [
      headers.map(escapeCsvValue).join(';'),
      ...comparisonData.map(row => [
        escapeCsvValue(row.name),
        escapeCsvValue(row.ticker),
        escapeCsvValue(row.maturity),
        escapeCsvValue(row.coupon),
        escapeCsvValue(row.price),
        escapeCsvValue(row.ytm),
        escapeCsvValue(row.couponToPrice),
        escapeCsvValue(row.regularDuration),
        escapeCsvValue(row.duration),
        escapeCsvValue(row.convexity),
        escapeCsvValue(row.priceChange),
        escapeCsvValue(row.spread),
        escapeCsvValue(row.gSpread),
        escapeCsvValue(row.zSpread),
      ].join(';')),
    ];

    const csvContent = csvRows.join('\n');
    
    // Add BOM for proper encoding in Excel (UTF-8)
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `comparison_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Handle import comparison bonds
  const handleImportComparison = (bonds: BondListItem[]) => {
    loadBondsToComparison(bonds);
  };

  // Handle clear comparison
  const handleClearComparison = () => {
    if (window.confirm('Вы уверены, что хотите удалить все облигации из сравнения?')) {
      clearComparison();
    }
  };

  // Calculate Total Return for a bond
  const calculateTotalReturn = (bond: BondListItem): TotalReturnResult | null => {
    // Validate required inputs
    if (
      bond.PREVPRICE === null || bond.PREVPRICE === undefined ||
      bond.FACEVALUE === null || bond.FACEVALUE === undefined ||
      bond.COUPONPERCENT === null || bond.COUPONPERCENT === undefined ||
      forecastRate === null || currentRate === null
    ) {
      return null;
    }

    // Use manual values if checkbox is checked and manual values are set, otherwise use bond data
    const manualValues = manualPrices.get(bond.SECID);
    const cleanPricePercent = useManualParams && manualValues 
      ? manualValues.cleanPricePercent 
      : bond.PREVPRICE;
    const nominal = bond.FACEVALUE;
    const accruedInterest = useManualParams && manualValues
      ? manualValues.accruedInterest
      : (bond.ACCRUEDINT ?? 0);
    const couponRate = bond.COUPONPERCENT / 100; // Convert to decimal
    const modDuration = calculateModifiedDuration(bond);

    if (modDuration === null) {
      return null;
    }

    // ===== DIRTY-TO-DIRTY METHOD =====
    // This method correctly accounts for accrued interest (НКД) at both purchase and sale,
    // ensuring that paid НКД is not incorrectly counted as profit.

    // Step 1: Calculate purchase costs (T0) - Dirty price at purchase
    const priceRub = nominal * (cleanPricePercent / 100);
    const accruedInterestAtPurchase = accruedInterest;
    const buyDirtyPrice = priceRub + accruedInterestAtPurchase;

    // Step 2: Calculate quantity and total invested
    const quantity = Math.floor(investAmount / buyDirtyPrice);
    const totalInvested = quantity * buyDirtyPrice;
    const cashBalance = investAmount - totalInvested;

    // Step 3: Calculate future price with convexity adjustment
    // Calculate delta yield: (targetYield - currentYield) / 100
    // If forecastRate (8%) < currentRate (16%), deltaYield is negative (-0.08)
    const deltaYield = (forecastRate - currentRate) / 100;
    
    // According to Fabozzi theory: PercentageChange = -ModDuration * deltaYield
    // When deltaYield is negative (rates decrease), priceChangePercent will be positive (price increases)
    const priceChangeDuration = -modDuration * deltaYield;
    
    // Calculate convexity adjustment: 0.5 * Convexity * deltaYield^2
    const convexity = calculateConvexity(bond);
    const priceChangeConvexity = convexity !== null 
      ? 0.5 * convexity * Math.pow(deltaYield, 2)
      : 0;
    
    // Total price change with convexity adjustment
    const totalPriceChangePercent = priceChangeDuration + priceChangeConvexity;
    
    // Future clean price in percentage
    const futureCleanPricePercent = cleanPricePercent * (1 + totalPriceChangePercent);

    // Step 4: Calculate sale proceeds (T_exit) - Dirty price at sale
    // For simplification, we use current accrued interest as accruedInterestAtSale
    // In a more precise calculation, this would be based on coupon dates and time elapsed
    const accruedInterestAtSale = accruedInterestAtPurchase; // Simplified: same as purchase
    const futurePriceRub = nominal * (futureCleanPricePercent / 100);
    const sellDirtyPrice = futurePriceRub + accruedInterestAtSale;
    const totalSaleProceeds = quantity * sellDirtyPrice;

    // Step 5: Calculate coupon income
    // Total gross coupons received during holding period (includes НКД in first coupon)
    const grossCouponsReceived = quantity * nominal * couponRate * years;
    
    // In Dirty-to-Dirty method: first coupon includes НКД that was paid at purchase
    // This НКД is a return of what we already paid, not new income
    // Therefore, we subtract the НКД paid at purchase from total coupons
    const accruedInterestPaid = quantity * accruedInterestAtPurchase;
    const totalCouponsReceived = grossCouponsReceived - accruedInterestPaid;

    // Step 6: Calculate final results using Dirty-to-Dirty method
    // Final balance = sale proceeds + coupons + cash balance
    const finalBalance = totalSaleProceeds + totalCouponsReceived + cashBalance;
    
    // Absolute profit = final balance - total invested (which includes НКД paid at purchase)
    // This ensures НКД paid at purchase is not counted as profit
    const absoluteProfit = finalBalance - totalInvested;
    
    // Total return percentage based on initial investment amount
    const totalReturnPercent = (absoluteProfit / investAmount) * 100;
    const annualReturn = (Math.pow(finalBalance / investAmount, 1 / years) - 1) * 100;

    return {
      secid: bond.SECID,
      name: bond.SHORTNAME || '—',
      ticker: bond.SECID || '—',
      investAmount: Math.round(investAmount * 100) / 100,
      cleanPricePercent: Math.round(cleanPricePercent * 100) / 100,
      nominal: Math.round(nominal * 100) / 100,
      accruedInterest: Math.round(accruedInterestAtPurchase * 100) / 100,
      couponRate: Math.round(couponRate * 10000) / 10000,
      years: Math.round(years * 100) / 100,
      modDuration: Math.round(modDuration * 100) / 100,
      targetYieldChange: Math.round(deltaYield * 10000) / 10000,
      priceRub: Math.round(priceRub * 100) / 100,
      dirtyPriceRub: Math.round(buyDirtyPrice * 100) / 100,
      quantity,
      cashBalance: Math.round(cashBalance * 100) / 100,
      totalCoupons: Math.round(totalCouponsReceived * 100) / 100,
      grossCouponsReceived: Math.round(grossCouponsReceived * 100) / 100,
      priceChangePercent: Math.round(totalPriceChangePercent * 10000) / 100,
      futureCleanPricePercent: Math.round(futureCleanPricePercent * 100) / 100,
      saleProceeds: Math.round(totalSaleProceeds * 100) / 100,
      finalBalance: Math.round(finalBalance * 100) / 100,
      absoluteProfit: Math.round(absoluteProfit * 100) / 100,
      totalReturnPercent: Math.round(totalReturnPercent * 100) / 100,
      annualReturn: Math.round(annualReturn * 100) / 100,
    };
  };

  // Handle manual price and accrued interest updates
  // These functions preserve the other parameter value when updating one
  const updateManualPrice = useCallback((secid: string, cleanPricePercent: number, currentAccruedInterest: number) => {
    setManualPrices(prev => {
      const newMap = new Map(prev);
      const existing = newMap.get(secid);
      // Use existing accruedInterest if available, otherwise use current from table data
      const accruedInterestToKeep = existing?.accruedInterest ?? currentAccruedInterest;
      newMap.set(secid, {
        cleanPricePercent,
        accruedInterest: accruedInterestToKeep,
      });
      return newMap;
    });
  }, []);

  const updateManualAccruedInterest = useCallback((secid: string, accruedInterest: number, currentCleanPricePercent: number) => {
    setManualPrices(prev => {
      const newMap = new Map(prev);
      const existing = newMap.get(secid);
      // Use existing cleanPricePercent if available, otherwise use current from table data
      const cleanPricePercentToKeep = existing?.cleanPricePercent ?? currentCleanPricePercent;
      newMap.set(secid, {
        cleanPricePercent: cleanPricePercentToKeep,
        accruedInterest,
      });
      return newMap;
    });
  }, []);

  // Calculate Total Return results for all bonds
  const totalReturnResults = useMemo(() => {
    if (comparisonBonds.length === 0 || forecastRate === null || currentRate === null) {
      return [];
    }

    return comparisonBonds
      .map(bond => calculateTotalReturn(bond))
      .filter((result): result is TotalReturnResult => result !== null);
  }, [comparisonBonds, investAmount, years, forecastRate, currentRate, useManualParams, manualPrices]);

  // Column definitions for Total Return results table
  const totalReturnColumnDefs: ColDef[] = useMemo(() => [
    {
      field: 'name',
      headerName: 'Название',
      minWidth: 150,
      cellStyle: { textAlign: 'left' },
      pinned: 'left',
    },
    {
      field: 'ticker',
      headerName: 'Тикер',
      minWidth: 100,
      cellStyle: { textAlign: 'center' },
    },
    {
      field: 'cleanPricePercent',
      headerName: 'Чистая цена, %',
      minWidth: 120,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      editable: useManualParams,
      valueSetter: (params) => {
        const newValue = typeof params.newValue === 'string' ? parseFloat(params.newValue) : params.newValue;
        if (!isNaN(newValue) && newValue !== null && newValue !== undefined) {
          params.data.cleanPricePercent = newValue;
          // Pass current accruedInterest from table data to preserve it
          updateManualPrice(params.data.secid, newValue, params.data.accruedInterest);
          return true;
        }
        return false;
      },
      valueParser: (params) => {
        const value = parseFloat(params.newValue);
        return isNaN(value) ? params.oldValue : value;
      },
    },
    {
      field: 'accruedInterest',
      headerName: 'НКД, руб.',
      minWidth: 100,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      editable: useManualParams,
      valueSetter: (params) => {
        const newValue = typeof params.newValue === 'string' ? parseFloat(params.newValue) : params.newValue;
        if (!isNaN(newValue) && newValue !== null && newValue !== undefined) {
          params.data.accruedInterest = newValue;
          // Pass current cleanPricePercent from table data to preserve it
          updateManualAccruedInterest(params.data.secid, newValue, params.data.cleanPricePercent);
          return true;
        }
        return false;
      },
      valueParser: (params) => {
        const value = parseFloat(params.newValue);
        return isNaN(value) ? params.oldValue : value;
      },
    },
    {
      field: 'couponRate',
      headerName: 'Купонная ставка',
      minWidth: 130,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value * 100, 2) + '%',
    },
    {
      field: 'modDuration',
      headerName: 'Модифицированная дюрация',
      minWidth: 180,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
    },
    {
      field: 'priceRub',
      headerName: 'Чистая цена, руб.',
      minWidth: 140,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
    },
    {
      field: 'dirtyPriceRub',
      headerName: 'Грязная цена покупки, руб.',
      minWidth: 180,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      headerTooltip: 'Грязная цена покупки (чистая цена + НКД) на момент покупки. Используется в методе Dirty-to-Dirty для корректного учета НКД.',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'quantity',
      headerName: 'Количество лотов',
      minWidth: 130,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => String(params.value),
    },
    {
      field: 'cashBalance',
      headerName: 'Остаток, руб.',
      minWidth: 120,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
    },
    {
      field: 'grossCouponsReceived',
      headerName: 'Полная сумма купонов (включая НКД в первом купоне), руб.',
      minWidth: 320,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      headerTooltip: 'Полная сумма всех купонных выплат за период владения облигацией. Включает НКД, который был уплачен продавцу при покупке и вернется в первом купоне. Это валовая сумма всех купонных выплат без вычета уплаченного НКД.',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'totalCoupons',
      headerName: 'Чистый доход от купонов (за вычетом уплаченного НКД), руб.',
      minWidth: 320,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      headerTooltip: 'Чистый доход от купонов за период владения облигацией, рассчитанный методом Dirty-to-Dirty. Из полной суммы купонов вычитается НКД, уплаченный при покупке (который вернется в первом купоне). Используется для корректного расчета прибыли.',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'priceChangePercent',
      headerName: 'Изменение цены, %',
      minWidth: 140,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2) + '%',
    },
    {
      field: 'futureCleanPricePercent',
      headerName: 'Прогнозная цена, %',
      minWidth: 140,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
    },
    {
      field: 'saleProceeds',
      headerName: 'Выручка от продажи (грязная цена), руб.',
      minWidth: 240,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => formatNumber(params.value, 2),
      headerTooltip: 'Выручка от продажи облигаций по грязной цене (прогнозная чистая цена + НКД на момент продажи). Используется в методе Dirty-to-Dirty.',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'finalBalance',
      headerName: 'Итоговая сумма, руб.',
      minWidth: 150,
      cellStyle: { textAlign: 'right', fontWeight: 600 },
      valueFormatter: (params) => formatNumber(params.value, 2),
    },
    {
      field: 'absoluteProfit',
      headerName: 'Абсолютная прибыль, руб.',
      minWidth: 170,
      cellStyle: { textAlign: 'right', fontWeight: 600 },
      valueFormatter: (params) => formatNumber(params.value, 2),
      headerTooltip: 'Абсолютная прибыль, рассчитанная методом Dirty-to-Dirty: (Выручка от продажи + Купоны + Остаток) - Затраты на покупку. Учитывает НКД при покупке и продаже, исключая двойной учет НКД в прибыли.',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'totalReturnPercent',
      headerName: 'Совокупная доходность (Total Return), %',
      minWidth: 200,
      cellStyle: { textAlign: 'right', fontWeight: 600 },
      valueFormatter: (params) => formatNumber(params.value, 2) + '%',
      headerTooltip: 'Совокупная доходность (Total Return), рассчитанная методом Dirty-to-Dirty. Отражает реальную доходность инвестиции с учетом всех затрат (включая уплаченный НКД) и всех доходов (включая полученный НКД при продаже).',
      headerComponent: CustomHeaderWithTooltip,
      headerClass: 'ag-header-center',
    },
    {
      field: 'annualReturn',
      headerName: 'Среднегодовая доходность (CAGR), %',
      minWidth: 220,
      cellStyle: { textAlign: 'right', fontWeight: 600 },
      valueFormatter: (params) => formatNumber(params.value, 2) + '%',
    },
  ] as ColDef[], [useManualParams, updateManualPrice, updateManualAccruedInterest]);

  if (comparisonBonds.length === 0) {
    return (
      <Card sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%',
        boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
        borderRadius: '12px',
      }}>
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
          <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-start', gap: 1, borderBottom: 1, borderColor: 'divider' }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<UploadFileIcon />}
              onClick={() => setIsImportDialogOpen(true)}
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabledBackground',
                },
              }}
            >
              Загрузить из файла
            </Button>
          </Box>
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Box sx={{ textAlign: 'center', p: 3 }}>
              <Typography variant="h6" color="text.secondary">
                Нет облигаций для сравнения
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Добавьте облигации к сравнению, используя столбец "Добавить к сравнению" в таблице скринера облигаций,
                или загрузите облигации из файла.
              </Typography>
            </Box>
          </Box>
        </CardContent>
        <ComparisonImportDialog
          open={isImportDialogOpen}
          onClose={() => setIsImportDialogOpen(false)}
          onImport={handleImportComparison}
        />
      </Card>
    );
  }

  if (isLoadingZerocupon || isLoadingCoupons) {
    return (
      <Card sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%',
        boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
        borderRadius: '12px',
      }}>
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LoadingSpinner message={isLoadingZerocupon ? "Загрузка данных кривой бескупонной доходности..." : "Загрузка данных о купонах..."} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column', 
      width: '100%',
      boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
      borderRadius: '12px',
    }}>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
        {/* Header with download buttons */}
        <Box sx={{ p: 1, display: 'flex', justifyContent: 'space-between', gap: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<UploadFileIcon />}
              onClick={() => setIsImportDialogOpen(true)}
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabledBackground',
                },
              }}
            >
              Загрузить из файла
            </Button>
            {currentTab === 1 && (
              <Button
                variant="outlined"
                size="small"
                onClick={() => setIsParamsDialogOpen(true)}
                sx={{
                  '&.Mui-disabled': {
                    color: 'text.disabled',
                    borderColor: 'action.disabledBackground',
                  },
                }}
              >
                Параметры расчета
              </Button>
            )}
            {comparisonData.length > 0 && currentTab === 0 && (
              <>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<SaveIcon />}
                  onClick={handleExportToCsv}
                  sx={{
                    '&.Mui-disabled': {
                      color: 'text.disabled',
                      borderColor: 'action.disabledBackground',
                    },
                  }}
                >
                  Сохранить в CSV
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownloadMarkdown}
                  sx={{
                    '&.Mui-disabled': {
                      color: 'text.disabled',
                      borderColor: 'action.disabledBackground',
                    },
                  }}
                >
                  Сохранить в Markdown
                </Button>
              </>
            )}
          </Box>
          {comparisonBonds.length > 0 && (
            <Button
              variant="outlined"
              size="small"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleClearComparison}
              disabled={comparisonBonds.length === 0}
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabledBackground',
                },
              }}
            >
              Очистить сравнение
            </Button>
          )}
        </Box>

        {/* Tabs Navigation */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
            <Tab label="Сравнение облигаций" />
            <Tab label="Расчет возможных денежных потоков" />
          </Tabs>
        </Box>

        {/* Tab Content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', height: '100%' }}>
          {currentTab === 0 && (
            /* Comparison Table */
            <Box sx={{ flexGrow: 1, display: 'flex', px: 2 }}>
          <Box
            className="ag-theme-material"
            sx={{
              height: '100%',
              width: '100%',
              ...(headerHeight && {
                '--ag-header-height': `${headerHeight}px`,
              }),
              // External border for table (Bootstrap .table-bordered style)
              '& .ag-root-wrapper': {
                border: '1px solid #dee2e6',
                borderRadius: '4px',
              },
              // Header with horizontal line
              '& .ag-header': {
                borderBottom: '1px solid #ddd',
              },
              '& .ag-header-cell': {
                display: 'flex',
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '8px 4px',
                boxSizing: 'border-box',
                gap: '0px !important',
                // Bootstrap-style borders
                borderRight: '1px solid #dee2e6 !important',
                borderBottom: '1px solid #dee2e6 !important',
                fontWeight: 600,
                color: '#444',
                background: '#fafafa',
              },
              '& .ag-header-cell:last-child': {
                borderRight: 'none !important',
              },
              '& .ag-header-cell-label': {
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                whiteSpace: 'normal',
                wordBreak: 'break-word',
                lineHeight: 1.5,
                flex: '0 1 auto',
                minWidth: 0,
                padding: '4px 0px 4px 8px !important',
                marginRight: '0px !important',
                marginLeft: '0px !important',
                marginTop: '0px !important',
                marginBottom: '0px !important',
                overflow: 'visible',
                boxSizing: 'border-box',
              },
              '& .ag-header-cell-text': {
                whiteSpace: 'normal',
                wordBreak: 'break-word',
                lineHeight: 1.5,
                textAlign: 'center',
                display: 'block',
                overflow: 'visible',
                hyphens: 'auto',
                marginRight: '0px !important',
                paddingRight: '0px !important',
              },
              '& .ag-header-cell-menu-button': {
                flexShrink: 0,
                alignSelf: 'center',
                marginLeft: '1px !important',
                marginRight: '0px !important',
                marginTop: '0px !important',
                marginBottom: '0px !important',
                padding: '0px !important',
                width: 'auto !important',
                minWidth: 'auto !important',
              },
              '& .ag-header-cell-filter-button': {
                flexShrink: 0,
                alignSelf: 'center',
                marginLeft: '1px !important',
                marginRight: '0px !important',
                marginTop: '0px !important',
                marginBottom: '0px !important',
                padding: '0px !important',
                width: 'auto !important',
                minWidth: 'auto !important',
              },
              '& .ag-header-cell-label + .ag-header-cell-menu-button': {
                marginLeft: '1px !important',
              },
              '& .ag-header-cell-label + .ag-header-cell-filter-button': {
                marginLeft: '1px !important',
              },
              '& .ag-header-cell-filtered .ag-header-cell-menu-button': {
                opacity: 1,
              },
              '& .ag-header-cell-filtered .ag-header-cell-filter-button': {
                opacity: 1,
              },
              '& .ag-cell': {
                // Bootstrap-style borders
                borderRight: '1px solid #dee2e6 !important',
                borderBottom: '1px solid #dee2e6 !important',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                lineHeight: '1.5 !important',
                padding: '8px 12px !important',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxHeight: '44px !important',
                height: '44px !important',
                boxSizing: 'border-box',
                '& > *': {
                  maxHeight: '36px !important',
                  overflow: 'hidden',
                },
              },
              '& .ag-row .ag-cell:last-child': {
                borderRight: 'none !important',
              },
              '& .ag-cell[col-id="name"]': {
                justifyContent: 'flex-start',
                textAlign: 'left !important',
              },
              // Ensure numeric columns are centered
              '& .ag-cell[col-id="ticker"], & .ag-cell[col-id="maturity"], & .ag-cell[col-id="coupon"], & .ag-cell[col-id="price"], & .ag-cell[col-id="ytm"], & .ag-cell[col-id="couponToPrice"], & .ag-cell[col-id="regularDuration"], & .ag-cell[col-id="duration"], & .ag-cell[col-id="convexity"], & .ag-cell[col-id="priceChange"], & .ag-cell[col-id="spread"], & .ag-cell[col-id="gSpread"], & .ag-cell[col-id="zSpread"], & .ag-cell[col-id="actions"]': {
                justifyContent: 'center',
                textAlign: 'center !important',
              },
              // Row styling - increased height for better readability
              '& .ag-row': {
                cursor: 'default',
                minHeight: '44px !important',
                maxHeight: '44px !important',
                height: '44px !important',
                '& > *': {
                  maxHeight: '44px !important',
                },
              },
              '& .ag-row-hover': {
                backgroundColor: '#f7f9fc !important',
              },
              // Center header class
              '& .ag-header-center .ag-header-cell-label': {
                justifyContent: 'center',
              },
              // Remove shadow from pinned-right sections to make it look like part of the table
              '& .ag-pinned-right-header': {
                boxShadow: 'none !important',
              },
              '& .ag-pinned-right-cols-container': {
                boxShadow: 'none !important',
              },
              // Make pinned-right cells look continuous with the rest of the table
              '& .ag-pinned-right-cols-container .ag-cell': {
                background: '#fff !important',
                borderRight: 'none !important',
              },
              '& .ag-pinned-right-header .ag-header-cell': {
                background: '#fafafa !important',
                borderRight: 'none !important',
              },
            }}
          >
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
              autoSizeStrategy={{
                type: 'fitGridWidth',
                defaultMinWidth: 80,
              }}
              suppressAggFuncInHeader={true}
              suppressMenuHide={true}
              getRowId={(params) => params.data.secid}
              theme="legacy"
            />
          </Box>
          </Box>
          )}

          {currentTab === 1 && (
            /* Cash Flow Calculation Tab */
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 2, minHeight: 0, overflow: 'auto' }}>

              {/* Results Table */}
              {forecastRate !== null && currentRate !== null ? (
                <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 1 }}>
                    Результаты расчета
                  </Typography>
                  <Box
                    className="ag-theme-material"
                    sx={{
                      flex: 1,
                      width: '100%',
                      minHeight: 0,
                      '& .ag-root-wrapper': {
                        border: '1px solid #dee2e6',
                        borderRadius: '4px',
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                      },
                      '& .ag-body': {
                        flex: 1,
                        minHeight: 0,
                        overflow: 'auto',
                      },
                      '& .ag-header': {
                        borderBottom: '1px solid #ddd',
                      },
                      '& .ag-header-cell': {
                        borderRight: '1px solid #dee2e6 !important',
                        borderBottom: '1px solid #dee2e6 !important',
                        fontWeight: 600,
                        background: '#fafafa',
                        minHeight: '44px',
                        height: 'auto',
                      },
                      '& .ag-header-cell-label': {
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        lineHeight: 1.4,
                        textAlign: 'center',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '8px 4px',
                        width: '100%',
                        height: '100%',
                        overflow: 'visible',
                      },
                      '& .ag-header-cell-text': {
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        lineHeight: 1.4,
                        textAlign: 'center',
                        overflow: 'visible',
                      },
                      '& .ag-cell': {
                        borderRight: '1px solid #dee2e6 !important',
                        borderBottom: '1px solid #dee2e6 !important',
                      },
                    }}
                  >
                    <AgGridReact<TotalReturnResult>
                      rowData={totalReturnResults}
                      columnDefs={totalReturnColumnDefs}
                      defaultColDef={{
                        sortable: true,
                        filter: true,
                        resizable: true,
                        autoHeaderHeight: true,
                        wrapHeaderText: true,
                      }}
                      animateRows={true}
                      pagination={true}
                      paginationPageSize={50}
                      enableCellTextSelection={true}
                      suppressRowClickSelection={true}
                      getRowId={(params) => params.data.secid}
                      theme="legacy"
                    />
                  </Box>
                </Box>
              ) : (
                <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    Заполните все поля для расчета
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </Box>
      </CardContent>
      {/* Parameters Calculation Dialog */}
      <Dialog
        open={isParamsDialogOpen}
        onClose={() => setIsParamsDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600 }}>
          Параметры расчета
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 6 }}>
                <TextField
                  fullWidth
                  label="Сумма инвестиций, руб."
                  type="number"
                  value={investAmount}
                  onChange={(e) => setInvestAmount(Number(e.target.value))}
                  inputProps={{ min: 0, step: 1000 }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 6 }}>
                <TextField
                  fullWidth
                  label="Горизонт расчета, лет"
                  type="number"
                  value={years}
                  onChange={(e) => setYears(Number(e.target.value))}
                  inputProps={{ min: 0.1, step: 0.1 }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 6 }}>
                <TextField
                  fullWidth
                  label="Предполагаемая ставка, %"
                  type="number"
                  value={forecastRate ?? ''}
                  onChange={(e) => setForecastRate(e.target.value ? Number(e.target.value) : null)}
                  inputProps={{ min: 0, step: 0.1 }}
                  helperText={
                    useForecastRate
                      ? (isLoadingForecast ? 'Загрузка из прогноза...' : 'Из прогноза Банка России')
                      : 'Введите значение вручную'
                  }
                  disabled={useForecastRate && isLoadingForecast}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 6 }}>
                <TextField
                  fullWidth
                  label="Текущая ставка ЦБ, %"
                  type="number"
                  value={currentRate ?? ''}
                  onChange={(e) => setCurrentRate(e.target.value ? Number(e.target.value) : null)}
                  inputProps={{ min: 0, step: 0.1 }}
                />
              </Grid>
            </Grid>
            <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={useForecastRate}
                    onChange={(e) => setUseForecastRate(e.target.checked)}
                  />
                }
                label="Использовать ставку из прогноза Банка России"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={useManualParams}
                    onChange={(e) => setUseManualParams(e.target.checked)}
                  />
                }
                label="Задать параметры вручную"
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsParamsDialogOpen(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>
      <ComparisonImportDialog
        open={isImportDialogOpen}
        onClose={() => setIsImportDialogOpen(false)}
        onImport={handleImportComparison}
      />
    </Card>
  );
};
