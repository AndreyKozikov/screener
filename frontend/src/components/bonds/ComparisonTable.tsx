import React, { useMemo, useState, useEffect } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Tooltip,
  Button,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useComparisonStore } from '../../stores/comparisonStore';
import { formatNumber } from '../../utils/formatters';
import { fetchZerocuponData, type ZerocuponRecord } from '../../api/zerocupon';
import {
  getLatestZerocuponRecord,
  buildYieldCurveMap,
  interpolateZeroCurveYield,
  calculateSpread,
  formatSpread,
} from '../../utils/zerocuponInterpolation';
import dayjs from 'dayjs';
import type { BondListItem } from '../../types/bond';
import { LoadingSpinner } from '../common/LoadingSpinner';

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
  priceChange: string;
  spread: string;
  secid: string; // Add secid for deletion
}

/**
 * ComparisonTable Component
 * 
 * Displays comparison table for selected bonds
 */
export const ComparisonTable: React.FC = () => {
  const { comparisonBonds, removeBondFromComparison } = useComparisonStore();
  const [zerocuponData, setZerocuponData] = useState<ZerocuponRecord[]>([]);
  const [isLoadingZerocupon, setIsLoadingZerocupon] = useState(false);

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

  // Format maturity date as "ГГГГ (Yг)"
  const formatMaturity = (matDate: string | null): string => {
    if (!matDate) return '—';
    
    try {
      const date = new Date(matDate);
      if (isNaN(date.getTime())) return '—';
      
      const year = date.getFullYear();
      const yearsToMaturity = calculateYearsToMaturity(matDate);
      
      if (yearsToMaturity === null) {
        return `${year}`;
      }
      
      // Round to 1 decimal place
      const roundedYears = Math.round(yearsToMaturity * 10) / 10;
      return `${year} (${roundedYears}г)`;
    } catch {
      return '—';
    }
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
  const calculateModifiedDuration = (bond: BondListItem): number | null => {
    if (bond.DURATION === null || bond.DURATION === undefined || bond.DURATION === 0) {
      return null;
    }
    
    // Convert from days to years (DURATION уже в днях)
    const durationYears = bond.DURATION / 365;
    
    // Modified Duration = D / (1 + YTM/100)
    if (bond.YIELDATPREVWAPRICE === null || bond.YIELDATPREVWAPRICE === undefined) {
      return durationYears;
    }
    
    const ytmDecimal = bond.YIELDATPREVWAPRICE / 100;
    const modifiedDuration = durationYears / (1 + ytmDecimal);
    
    return modifiedDuration;
  };

  // Calculate price change for -1% rate change
  const calculatePriceChange = (bond: BondListItem): number | null => {
    const md = calculateModifiedDuration(bond);
    if (md === null) return null;
    
    // PriceChangePercent = MD * 1 (where 1 = 1% change)
    return md * 1;
  };

  // Format price change as "+X,XX%"
  const formatPriceChange = (value: number | null): string => {
    if (value === null || value === undefined || isNaN(value)) return '—';
    
    const rounded = Math.round(value * 100) / 100;
    const sign = rounded >= 0 ? '+' : '';
    return `${sign}${rounded.toFixed(2)}%`;
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
          priceChange,
          spread: '—',
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
      
      const priceChange = formatPriceChange(calculatePriceChange(bond));

      // Calculate spread
      const horizon = calculateYearsToMaturity(bond.MATDATE);
      let spreadStr = '—';
      
      if (horizon !== null && horizon > 0) {
        const zeroCurveYield = interpolateZeroCurveYield(yieldCurveMap, horizon);
        if (zeroCurveYield !== null) {
          const spread = calculateSpread(bond.YIELDATPREVWAPRICE, zeroCurveYield);
          spreadStr = formatSpread(spread);
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
        priceChange,
        spread: spreadStr,
        secid: bond.SECID,
      };
    });
  }, [comparisonBonds, zerocuponData]);

  // Generate markdown table
  const generateMarkdown = (): string => {
    const headers = [
      'Название',
      'Тикер',
      'Погашение',
      'Цена (%)',
      'Доходность к погашению (%)',
      'Доходность купона относительно номинала (%)',
      'Доходность купона к текущей цене (%)',
      'Дюрация',
      'Модифицированная дюрация',
      'Изменение цены при изменении ставки на 1%',
      'Премии и отклонения по рынку',
    ];
    
    // Calculate column widths for alignment
    const colWidths = headers.map((header, colIndex) => {
      let maxWidth = header.length;
      comparisonData.forEach((row) => {
        const values = [
          row.name,
          row.ticker,
          row.maturity,
          row.price,
          row.ytm,
          row.coupon,
          row.couponToPrice,
          row.regularDuration,
          row.duration,
          row.priceChange,
          row.spread,
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
        row.price,
        row.ytm,
        row.coupon,
        row.couponToPrice,
        row.regularDuration,
        row.duration,
        row.priceChange,
        row.spread,
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

  // Handle remove bond
  const handleRemoveBond = (secid: string) => {
    removeBondFromComparison(secid);
  };

  if (comparisonBonds.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          Нет облигаций для сравнения
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Добавьте облигации к сравнению, используя столбец "Добавить к сравнению" в таблице скринера облигаций
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header with download button */}
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6">
          Сравнение облигаций ({comparisonBonds.length})
        </Typography>
        {comparisonData.length > 0 && (
          <Button startIcon={<DownloadIcon />} onClick={handleDownloadMarkdown} variant="outlined">
            Сохранить в Markdown
          </Button>
        )}
      </Box>

      {/* Table */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <TableContainer component={Paper} sx={{ height: '100%' }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Название</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Тикер</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Погашение</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Цена (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Доходность к погашению (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Доходность купона относительно номинала (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Доходность купона к текущей цене (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Дюрация</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Модифицированная дюрация</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Изменение цены при изменении ставки на 1%</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                    Премии и отклонения по рынку
                    <Tooltip
                      title={
                        <Box sx={{ p: 0.5 }}>
                          <Typography variant="body2" sx={{ mb: 1 }}>
                            Показывает отклонение доходности облигации от расчетной рыночной доходности сопоставимых выпусков (по сроку до погашения и кредитному качеству).
                          </Typography>
                          <Typography variant="body2" sx={{ mb: 1 }}>
                            <strong>Положительное значение</strong> — облигация предлагает доходность выше рыночной нормы: рынок закладывает дополнительную премию, выпуск выглядит относительно недооценённым.
                          </Typography>
                          <Typography variant="body2" sx={{ mb: 1 }}>
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
                      <HelpOutlineIcon sx={{ fontSize: 16, color: 'text.secondary', cursor: 'help' }} />
                    </Tooltip>
                  </Box>
                </TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoadingZerocupon ? (
                <TableRow>
                  <TableCell colSpan={12} align="center">
                    <LoadingSpinner message="Загрузка данных кривой бескупонной доходности..." />
                  </TableCell>
                </TableRow>
              ) : comparisonData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={12} align="center">
                    <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                      Нет данных для отображения
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                comparisonData.map((row, index) => (
                  <TableRow key={row.secid} hover>
                    <TableCell align="left">{row.name}</TableCell>
                    <TableCell align="center">{row.ticker}</TableCell>
                    <TableCell align="center">{row.maturity}</TableCell>
                    <TableCell align="center">{row.price}</TableCell>
                    <TableCell align="center">{row.ytm}</TableCell>
                    <TableCell align="center">{row.coupon}</TableCell>
                    <TableCell align="center">{row.couponToPrice}</TableCell>
                    <TableCell align="center">{row.regularDuration}</TableCell>
                    <TableCell align="center">{row.duration}</TableCell>
                    <TableCell align="center">{row.priceChange}</TableCell>
                    <TableCell 
                      align="center"
                      sx={{
                        color: getSpreadColor(row.spread),
                        fontWeight: isSpreadNonZero(row.spread) ? 600 : 'inherit',
                      }}
                    >
                      {row.spread}
                    </TableCell>
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveBond(row.secid)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Box>
  );
};

