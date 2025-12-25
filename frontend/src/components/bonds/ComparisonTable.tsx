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
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import SaveIcon from '@mui/icons-material/Save';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useComparisonStore } from '../../stores/comparisonStore';
import { ComparisonImportDialog } from './ComparisonImportDialog';
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
  priceChange: string;
  spread: string;
  secid: string;
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
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const gridRef = useRef<AgGridReact<ComparisonRow>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);

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
        headerComponent: CustomHeaderWithTooltip,
        autoHeaderHeight: true,
      },
      {
        field: 'priceChange',
        headerName: 'Изменение цены при изменении ставки на 1%',
        minWidth: 180,
        cellStyle: { textAlign: 'center' },
        headerClass: 'ag-header-center',
        headerComponent: CustomHeaderWithTooltip,
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
          row.coupon,
          row.price,
          row.ytm,
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
        row.coupon, // Доходность купона относительно номинала (%)
        row.price, // Цена (%)
        row.ytm, // Доходность к погашению, YTM (%)
        row.couponToPrice, // Доходность купона к текущей цене (%)
        row.regularDuration, // Дюрация
        row.duration, // Модифицированная дюрация
        row.priceChange, // Изменение цены при изменении ставки на 1%
        row.spread, // Премии и отклонения по рынку
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
      'Изменение цены при изменении ставки на 1%',
      'Премии и отклонения по рынку',
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
        escapeCsvValue(row.priceChange),
        escapeCsvValue(row.spread),
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

  if (isLoadingZerocupon) {
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
            <LoadingSpinner message="Загрузка данных кривой бескупонной доходности..." />
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
            {comparisonData.length > 0 && (
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
              </>
            )}
          </Box>
        </Box>

        {/* Table */}
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
              '& .ag-cell[col-id="ticker"], & .ag-cell[col-id="maturity"], & .ag-cell[col-id="coupon"], & .ag-cell[col-id="price"], & .ag-cell[col-id="ytm"], & .ag-cell[col-id="couponToPrice"], & .ag-cell[col-id="regularDuration"], & .ag-cell[col-id="duration"], & .ag-cell[col-id="priceChange"], & .ag-cell[col-id="spread"], & .ag-cell[col-id="actions"]': {
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
            />
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
};
