import React, { useEffect, useMemo, useCallback, useState, useRef, useImperativeHandle } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, RowClickedEvent, CellClickedEvent, ICellRendererParams, IHeaderParams } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import './ag-grid-tooltips.css';
import { Box, Card, CardContent, Tooltip, IconButton } from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import RefreshIcon from '@mui/icons-material/Refresh';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import FullscreenExitIcon from '@mui/icons-material/FullscreenExit';
import CloseIcon from '@mui/icons-material/Close';
import SaveIcon from '@mui/icons-material/Save';
import InsightsIcon from '@mui/icons-material/Insights';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);
import { useBondsStore } from '../../stores/bondsStore';
import { useFiltersStore } from '../../stores/filtersStore';
import { useUiStore } from '../../stores/uiStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { fetchBonds } from '../../api/bonds';
import { fetchDescriptions } from '../../api/metadata';
import type { DescriptionsResponse } from '../../api/metadata';
import { 
  formatNumber, 
  formatPercent, 
  calculateCouponYieldToPrice,
  calculateCouponFrequency 
} from '../../utils/formatters';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import { EmptyState } from '../common/EmptyState';
import type { BondListItem } from '../../types/bond';
import { exportSelectedBonds } from '../../utils/bondExport';
import { ComparisonAnalysisDialog } from './ComparisonAnalysisDialog';
import AddToPortfolioRenderer from './AddToPortfolioRenderer';

type FieldDescriptionMap = Record<string, string>;

// Export selected bonds for use in parent component
export type BondsTableRef = {
  getSelectedBonds: () => Set<string>;
};

export type BondsTableProps = {
  onOpenFilters?: () => void;
};

const flattenDescriptions = (descriptions: DescriptionsResponse): FieldDescriptionMap => {
  const result: FieldDescriptionMap = {};

  Object.values(descriptions).forEach((section) => {
    if (section && typeof section === 'object' && !Array.isArray(section)) {
      Object.entries(section).forEach(([field, description]) => {
        if (typeof description === 'string' && description.trim().length > 0) {
          result[field] = description;
        }
      });
    }
  });

  return result;
};

/**
 * Нормализует рейтинг, удаляя префиксы, суффиксы и локальные индикаторы
 * Оставляет только основную буквенную часть: AAA, AA, A, BBB, BB, B, CCC, CC, C, D
 * 
 * Примеры:
 * "ruAAA" → "AAA"
 * "AAA(RU)" → "AAA"
 * "ruBBB+.sf" → "BBB"
 * "ruAA-" → "AA"
 * "A(RU)" → "A"
 * "BBB+" → "BBB"
 * "CCC-" → "CCC"
 */
const normalizeRating = (rating: string): string => {
  if (!rating || rating.trim() === '' || rating === '—' || rating === '-') {
    return '';
  }
  
  // Привести к верхнему регистру и убрать пробелы
  let normalized = rating.toUpperCase().trim();
  
  // Удалить префиксы: RU, (RU) в начале строки
  normalized = normalized.replace(/^RU\s*/i, '');
  normalized = normalized.replace(/^\(RU\)\s*/i, '');
  
  // Удалить все скобки и их содержимое (включая (RU) в любом месте)
  normalized = normalized.replace(/\([^)]*\)/g, '');
  
  // Удалить суффиксы: .SF, -SF, .sf в конце
  normalized = normalized.replace(/[.\-]?SF$/i, '');
  normalized = normalized.replace(/\.sf$/i, '');
  
  // Удалить знаки + и - в конце
  normalized = normalized.replace(/[+\-]+$/, '');
  
  // Удалить все точки и дефисы
  normalized = normalized.replace(/[.\-]/g, '');
  
  // Извлечь основную буквенную часть (AAA, AA, A, BBB, BB, B, CCC, CC, C, D)
  const letterMatch = normalized.match(/^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)/);
  if (letterMatch) {
    return letterMatch[1];
  }
  
  // Если точного совпадения нет, попробуем извлечь только буквы и найти паттерн
  const lettersOnly = normalized.replace(/[^A-Z]/g, '');
  const patternMatch = lettersOnly.match(/^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)/);
  if (patternMatch) {
    return patternMatch[1];
  }
  
  // Если ничего не найдено, вернуть пустую строку
  return '';
};

/**
 * Определяет цвет рейтинга на основе нормализованного значения
 * 
 * Цветовая схема:
 * - AAA, AA, A → зелёный (#4CAF50)
 * - BBB → жёлтый (#FFB300)
 * - BB, B → оранжевый (#FB8C00)
 * - CCC, CC, C, D → красный (#E53935)
 * - пустой/неопознанный → серый (#E0E0E0)
 */
const getRatingColor = (rating: string | null | undefined): { bg: string; color: string } => {
  if (!rating || rating.trim() === '' || rating === '—' || rating === '-') {
    return { bg: '#E0E0E0', color: '#666' };
  }
  
  // Нормализовать рейтинг
  const normalized = normalizeRating(rating);
  
  if (!normalized) {
    return { bg: '#E0E0E0', color: '#666' };
  }
  
  // Проверяем в порядке от более длинных к более коротким для правильного определения
  
  // AAA → зелёный (проверяем первым, так как это самое длинное)
  if (normalized.startsWith('AAA')) {
    return { bg: '#4CAF50', color: '#fff' };
  }
  
  // AA → зелёный
  if (normalized.startsWith('AA')) {
    return { bg: '#4CAF50', color: '#fff' };
  }
  
  // BBB → жёлтый (проверяем перед BB)
  if (normalized.startsWith('BBB')) {
    return { bg: '#FFB300', color: '#000' };
  }
  
  // CCC → красный (проверяем перед CC)
  if (normalized.startsWith('CCC')) {
    return { bg: '#E53935', color: '#fff' };
  }
  
  // CC → красный
  if (normalized.startsWith('CC')) {
    return { bg: '#E53935', color: '#fff' };
  }
  
  // BB → оранжевый
  if (normalized.startsWith('BB')) {
    return { bg: '#FB8C00', color: '#fff' };
  }
  
  // A → зелёный
  if (normalized === 'A') {
    return { bg: '#4CAF50', color: '#fff' };
  }
  
  // B → оранжевый
  if (normalized === 'B') {
    return { bg: '#FB8C00', color: '#fff' };
  }
  
  // C → красный
  if (normalized === 'C') {
    return { bg: '#E53935', color: '#fff' };
  }
  
  // D → красный
  if (normalized === 'D') {
    return { bg: '#E53935', color: '#fff' };
  }
  
  // Неопознанный рейтинг → серый
  return { bg: '#E0E0E0', color: '#666' };
};


/**
 * BondsTable Component
 * 
 * Main data table displaying bonds using AG Grid
 */
export const BondsTable = React.forwardRef<BondsTableRef, BondsTableProps>(({ onOpenFilters }, ref) => {
  const { bonds, isLoading, error, setBonds, setLoading, setError } = useBondsStore();
  const { filters } = useFiltersStore();
  const setSelectedBond = useUiStore((state) => state.setSelectedBond);
  const dataRefreshVersion = useUiStore((state) => state.dataRefreshVersion);
  const triggerDataRefresh = useUiStore((state) => state.triggerDataRefresh);
  const portfolioBonds = usePortfolioStore((state) => state.portfolioBonds);
  const [fieldDescriptions, setFieldDescriptions] = useState<FieldDescriptionMap>({});
  const metadataLoadedRef = useRef(false);
  const gridRef = useRef<AgGridReact<BondListItem>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);
  const [selectedBonds, setSelectedBonds] = useState<Set<string>>(new Set());
  const [isComparisonDialogOpen, setIsComparisonDialogOpen] = useState(false);
  const [comparisonDialogKey, setComparisonDialogKey] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isClosed, setIsClosed] = useState(false);

  // Load field descriptions
  useEffect(() => {
    if (metadataLoadedRef.current) {
      return;
    }

    let isCancelled = false;

    const loadMetadata = async () => {
      try {
        const descriptionsResponse = await fetchDescriptions();
        if (!isCancelled) {
          setFieldDescriptions(flattenDescriptions(descriptionsResponse));
          metadataLoadedRef.current = true;
        }
      } catch (err: unknown) {
        console.error('Failed to load field descriptions:', err);
      }
    };

    void loadMetadata();

    return () => {
      isCancelled = true;
    };
  }, []);

  // Load bonds data
  const loadBonds = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetchBonds(filters);
      setBonds(response);
      
      // Explicitly refresh AG Grid data after loading
      if (gridRef.current?.api) {
        // Small delay to ensure state is updated
        setTimeout(() => {
          if (gridRef.current?.api) {
            // Refresh all cells to ensure data is displayed
            gridRef.current.api.refreshCells({ force: true });
            // Resize columns to fit new data
            gridRef.current.api.sizeColumnsToFit();
          }
        }, 100);
      }
    } catch (error) {
      console.error('Error loading bonds:', error);
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError('Failed to load bonds');
      }
    } finally {
      setLoading(false);
    }
  }, [filters, setBonds, setLoading, setError]);

  // Load on mount and filter changes
  useEffect(() => {
    let isMounted = true;
    let isLoading = false;
    
    const loadData = async () => {
      // Prevent duplicate loads
      if (isLoading) {
        return;
      }
      
      try {
        isLoading = true;
        await loadBonds();
      } catch (error) {
        if (isMounted) {
          console.error('Error in loadBonds effect:', error);
        }
      } finally {
        if (isMounted) {
          isLoading = false;
        }
      }
    };
    
    loadData();
    
    return () => {
      isMounted = false;
      isLoading = false;
    };
  }, [loadBonds, dataRefreshVersion]);

  // Get field description helper
  const getFieldDescription = useCallback((field: string): string | undefined => {
    const direct = fieldDescriptions[field];
    if (direct) {
      return direct;
    }

    // Handle special cases
    if (field === 'COUPON_YIELD_TO_PRICE') {
      return fieldDescriptions['COUPONPERCENT'] || undefined;
    }
    if (field === 'COUPONPERCENT_NOMINAL') {
      return fieldDescriptions['COUPONPERCENT'] || undefined;
    }
    if (field.endsWith('BP')) {
      const trimmed = field.slice(0, -2);
      return fieldDescriptions[trimmed];
    }

    return undefined;
  }, [fieldDescriptions]);

  // Custom header component with Material-UI Tooltip
  const CustomHeaderWithTooltip = React.memo((params: IHeaderParams) => {
    const displayName = params.displayName || '';
    const tooltipText = params.column?.getColDef().headerTooltip as string | undefined;
    
    // Если нет tooltip, просто возвращаем стандартный заголовок
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

  // Column definitions
  const columnDefs: ColDef[] = useMemo(() => {
    // Custom cell renderer for SHORTNAME with PUT/CALL superscripts
    const ShortNameRenderer = (params: ICellRendererParams<BondListItem>) => {
      const bond = params.data;
      if (!bond) return null;

      const hasCall = bond.CALLOPTIONDATE != null && bond.CALLOPTIONDATE !== '';
      const hasPut = bond.PUTOPTIONDATE != null && bond.PUTOPTIONDATE !== '';

      return (
        <Box
          component="span"
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0,
          }}
        >
          <span>{bond.SHORTNAME}</span>
          {hasCall && (
            <Box
              component="span"
              sx={{
                fontSize: '0.7em',
                fontWeight: 700,
                color: '#1976d2',
                ml: 1,
              }}
            >
              CALL
            </Box>
          )}
          {hasPut && (
            <Box
              component="span"
              sx={{
                fontSize: '0.7em',
                fontWeight: 700,
                color: '#d32f2f',
                ml: hasCall ? 0.5 : 1,
              }}
            >
              PUT
            </Box>
          )}
        </Box>
      );
    };

    // Base column definition with common properties
    const createColumnDef = (field: string, headerName: string, otherProps: Partial<ColDef> = {}): ColDef => {
      const tooltipText = otherProps.headerTooltip !== undefined ? otherProps.headerTooltip : getFieldDescription(field);
      
      // Remove cellStyle from otherProps to avoid conflicts
      const { cellStyle: otherCellStyle, ...restProps } = otherProps;
      
      // Create cellStyle without undefined properties
      let cellStyle: ColDef['cellStyle'];
      if (otherCellStyle !== undefined) {
        if (typeof otherCellStyle === 'function') {
          cellStyle = otherCellStyle;
        } else if (typeof otherCellStyle === 'object') {
          // Filter out undefined properties
          const filtered = Object.fromEntries(
            Object.entries(otherCellStyle).filter(([_, value]) => value !== undefined)
          );
          cellStyle = filtered as Record<string, string | number>;
        }
      } else {
        cellStyle = { textAlign: 'center' };
      }
      
      return {
        field,
        headerName,
        headerClass: 'ag-header-center',
        // Используем кастомный header component с Material-UI Tooltip
        headerComponent: tooltipText ? CustomHeaderWithTooltip : undefined,
        headerTooltip: tooltipText, // Оставляем для совместимости
        // Center align cell content by default (can be overridden in otherProps)
        cellStyle,
        ...restProps,
      };
    };

    return [
    {
      field: 'checkbox',
      headerName: '',
      checkboxSelection: true,
      headerCheckboxSelection: false,
      width: 50,
      pinned: 'left',
      sortable: false,
      filter: false,
      suppressMenu: true,
      cellStyle: { textAlign: 'center' } as Record<string, string | number>,
    },
    createColumnDef('SHORTNAME', 'Название', {
      minWidth: 120,
      pinned: 'left',
      cellRenderer: ShortNameRenderer,
      cellStyle: { textAlign: 'left' }, // Left align for name column
      headerTooltip: getFieldDescription('SHORTNAME'),
      autoHeaderHeight: true,
    }),
    createColumnDef('RATING', 'Рейтинг', {
      minWidth: 100,
      pinned: 'left',
      valueGetter: (params) => {
        const bond = params.data;
        if (!bond) {
          return null;
        }
        // Use RATING_LEVEL from bond data (loaded from bonds_rating.json)
        return bond.RATING_LEVEL || null;
      },
      cellRenderer: (params: ICellRendererParams<BondListItem>) => {
        const rating = params.value;
        if (!rating) {
          return '—';
        }
        const { bg, color } = getRatingColor(rating);
        return (
          <Box
            sx={{
              px: 1,
              py: 0.5,
              borderRadius: '6px',
              fontSize: '12px',
              backgroundColor: bg,
              color: color,
              fontWeight: 600,
              display: 'inline-block',
              textAlign: 'center',
              minWidth: '50px',
            }}
          >
            {rating}
          </Box>
        );
      },
      cellStyle: { textAlign: 'center' },
      headerTooltip: 'Рейтинг облигации от рейтинговых агентств',
      autoHeaderHeight: true,
      sortable: false,
      filter: false,
    }),
    createColumnDef('PREVPRICE', 'Текущая цена', {
      minWidth: 100,
      valueFormatter: (params) => formatNumber(params.value, 2),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('PREVPRICE'),
      autoHeaderHeight: true,
    }),
    createColumnDef('COUPON_YIELD_TO_PRICE', 'Доходность купона к текущей цене', {
      minWidth: 120,
      valueGetter: (params) => {
        const bond = params.data;
        if (!bond) return null;
        // Calculate coupon frequency (payments per year)
        const couponFrequency = calculateCouponFrequency(bond.COUPONPERIOD);
        // Calculate yield: (COUPONVALUE / (PREVPRICE × FACEVALUE / 100)) × (payments per year) × 100
        return calculateCouponYieldToPrice(bond.COUPONVALUE, bond.PREVPRICE, bond.FACEVALUE, couponFrequency);
      },
      valueFormatter: (params) => formatPercent(params.value),
      type: 'numericColumn',
      headerTooltip: 'Рассчитывается как (Размер купона / (Текущая цена × Номинал / 100)) × (Число выплат в год) × 100',
      autoHeaderHeight: true,
    }),
    createColumnDef('YIELDATPREVWAPRICE', 'Доходность к погашению при текущей цене', {
      minWidth: 140,
      valueFormatter: (params) => formatPercent(params.value),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('YIELDATPREVWAPRICE'),
      autoHeaderHeight: true,
    }),
    createColumnDef('FACEVALUE', 'Номинальная стоимость', {
      minWidth: 100,
      valueFormatter: (params) => formatNumber(params.value, 0),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('FACEVALUE'),
      autoHeaderHeight: true,
    }),
    createColumnDef('FACEUNIT', 'Валюта', {
      minWidth: 60,
      valueGetter: (params) => params.data?.FACEUNIT ?? null,
      valueFormatter: (params) => params.value || '-',
      headerTooltip: getFieldDescription('FACEUNIT') || 'Валюта номинала',
      autoHeaderHeight: true,
    }),
    createColumnDef('COUPONPERCENT', 'Купон', {
      minWidth: 100,
      valueGetter: (params) => params.data?.COUPONVALUE ?? null,
      valueFormatter: (params) => {
        if (params.value == null || params.value === undefined) return '-';
        return formatNumber(params.value, 2);
      },
      type: 'numericColumn',
      headerTooltip: 'Сумма купона в рублях из данных о купонных выплатах',
      autoHeaderHeight: true,
    }),
    createColumnDef('COUPONPERCENT_NOMINAL', 'Доходность купона относительно номинала', {
      minWidth: 130,
      valueGetter: (params) => params.data?.COUPONPERCENT ?? null,
      valueFormatter: (params) => formatPercent(params.value),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('COUPONPERCENT_NOMINAL') || getFieldDescription('COUPONPERCENT'),
      autoHeaderHeight: true,
    }),
    createColumnDef('COUPONPERIOD', 'Частота купона', {
      minWidth: 80,
      valueGetter: (params) => {
        const bond = params.data;
        if (!bond) return null;
        return calculateCouponFrequency(bond.COUPONPERIOD);
      },
      valueFormatter: (params) => formatNumber(params.value, 0),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('COUPONPERIOD'),
      autoHeaderHeight: true,
    }),
    createColumnDef('ACCRUEDINT', 'НКД', {
      minWidth: 80,
      valueFormatter: (params) => formatNumber(params.value, 2),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('ACCRUEDINT'),
      autoHeaderHeight: true,
    }),
    createColumnDef('DURATION_YEARS', 'Дюрация, лет', {
      minWidth: 80,
      valueGetter: (params) => {
        const bond = params.data;
        if (!bond || bond.DURATION == null || bond.DURATION === undefined) return null;
        // Если дюрация равна 0, возвращаем null для отображения прочерка
        if (bond.DURATION === 0) return null;
        // Преобразование из дней в годы: DURATION / 365
        return bond.DURATION / 365;
      },
      valueFormatter: (params) => {
        if (params.value == null || params.value === undefined) return '-';
        return formatNumber(params.value, 2);
      },
      type: 'numericColumn',
      headerTooltip: getFieldDescription('DURATION') || 'Дюрация, лет',
      autoHeaderHeight: true,
    }),
    {
      field: 'addToPortfolio',
      headerName: 'Добавить в портфель',
      minWidth: 150,
      width: 150,
      pinned: 'right',
      sortable: false,
      filter: false,
      suppressMenu: true,
      resizable: false, // Prevent column resizing to avoid layout shifts
      cellRenderer: AddToPortfolioRenderer,
      cellStyle: { textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center' },
      cellClass: 'portfolio-action-cell', // Add class for easier identification
      headerClass: 'ag-header-center',
      autoHeaderHeight: true,
      suppressSizeToFit: true, // Prevent auto-sizing to avoid layout shifts
    },
    ];
  }, [getFieldDescription]);

  // Default column properties
  const defaultColDef: ColDef = useMemo(() => ({
    sortable: true,
    filter: true,
    resizable: true,
    minWidth: 80,
      suppressSizeToFit: false,
      autoHeaderHeight: true,
    }), []);

  // Stable reference to AddToPortfolioRenderer to prevent column redefinition
  // const addToPortfolioRenderer = useMemo(() => AddToPortfolioRenderer, []);

  // Track if cell click was on portfolio column to prevent row click
  const portfolioCellClickedRef = useRef(false);

  // Handle cell click - intercept clicks on portfolio column
  const onCellClicked = useCallback((event: CellClickedEvent) => {
    // If clicking on "Add to Portfolio" column, mark it and prevent row click
    if (event.column && event.column.getColId() === 'addToPortfolio') {
      portfolioCellClickedRef.current = true;
      // Prevent event propagation
      if (event.event) {
        event.event.stopPropagation();
        event.event.preventDefault();
      }
      // Reset flag after a short delay to allow row click check
      setTimeout(() => {
        portfolioCellClickedRef.current = false;
      }, 200);
      return;
    }
  }, []);

  // Handle row click - don't interfere with checkbox selection
  const onRowClicked = useCallback((event: RowClickedEvent) => {
    // Only open details, don't change checkbox selection
    // Checkbox selection is handled separately by AG Grid
    if (event.event && (event.event.target as HTMLElement).closest('.ag-checkbox')) {
      // If clicking on checkbox, let AG Grid handle it
      return;
    }
    
    // Get the clicked element FIRST - we need it for all checks
    const target = event.event?.target as HTMLElement | null;
    if (!target || !event.event) {
      return;
    }
    
    // PRIORITY CHECK: Don't open details if portfolio cell was clicked
    // Check 1: Portfolio cell clicked flag (set by onCellClicked)
    if (portfolioCellClickedRef.current) {
      return;
    }
    
    // Check 2: data-portfolio-cell attribute in click path
    if (target.closest('[data-portfolio-cell]')) {
      return;
    }
    
    // Check 4: Find the cell element that was clicked and check its col-id
    const clickedCell = target.closest('.ag-cell');
    if (clickedCell) {
      const colId = clickedCell.getAttribute('col-id');
      if (colId === 'addToPortfolio') {
        return;
      }
      // Also check by CSS class
      if (clickedCell.classList.contains('portfolio-action-cell')) {
        return;
      }
    }
    
    // Check 5: Walk up DOM tree to find any portfolio column cell
    let currentElement: HTMLElement | null = target;
    while (currentElement) {
      if (currentElement.classList.contains('ag-cell')) {
        const colId = currentElement.getAttribute('col-id');
        if (colId === 'addToPortfolio') {
          return;
        }
        if (currentElement.classList.contains('portfolio-action-cell')) {
          return;
        }
      }
      // Stop at row level to avoid going too far up
      if (currentElement.classList.contains('ag-row')) {
        break;
      }
      currentElement = currentElement.parentElement;
    }
    
    // If all checks passed, open bond details
    setSelectedBond(event.data.SECID);
  }, [setSelectedBond]);

  // Handle selection change
  const onSelectionChanged = useCallback(() => {
    if (gridRef.current?.api) {
      const selectedRows = gridRef.current.api.getSelectedRows() as BondListItem[];
      const selectedSecids = new Set(selectedRows.map(row => row.SECID));
      setSelectedBonds(selectedSecids);
    }
  }, []);

  // Calculate dynamic header height based on content
  const calculateHeaderHeight = useCallback(() => {
    const gridContainer = document.querySelector<HTMLElement>('.ag-theme-material');
    if (!gridContainer) return;

    const headerCells = gridContainer.querySelectorAll<HTMLElement>('.ag-header-cell');
    if (headerCells.length === 0) return;

    let maxContentHeight = 0;

    // Measure each header cell's content height
    headerCells.forEach((cell) => {
      const label = cell.querySelector<HTMLElement>('.ag-header-cell-label');
      if (!label) return;

      // Temporarily set height to auto to measure content
      const originalDisplay = label.style.display;
      const originalHeight = label.style.height;
      const originalOverflow = label.style.overflow;
      
      label.style.display = 'block';
      label.style.height = 'auto';
      label.style.overflow = 'visible';

      // Measure the scroll height (actual content height)
      const contentHeight = label.scrollHeight;
      
      // Restore original styles
      label.style.display = originalDisplay;
      label.style.height = originalHeight;
      label.style.overflow = originalOverflow;

      if (contentHeight > maxContentHeight) {
        maxContentHeight = contentHeight;
      }
    });

    // Calculate total header height: content + padding + borders
    // Padding: 8px top + 8px bottom = 16px, plus cell padding: 4px + 4px = 8px
    const calculatedHeight = Math.max(Math.ceil(maxContentHeight) + 24, 60);

    // Update header height if it changed
    if (calculatedHeight !== headerHeight) {
      setHeaderHeight(calculatedHeight);
      
      // Also update CSS variable for AG Grid
      gridContainer.style.setProperty('--ag-header-height', `${calculatedHeight}px`);
      
      // Force AG Grid to recalculate header height
      if (gridRef.current?.api) {
        gridRef.current.api.sizeColumnsToFit();
      }
    }
  }, [headerHeight]);

  // Handle grid ready
  const onGridReady = useCallback(() => {
    if (gridRef.current?.api) {
      // Auto-size all columns to fit content
      gridRef.current.api.autoSizeAllColumns(false); // false = exclude header from calculation
      
      // Calculate header height after headers are rendered
      setTimeout(() => {
        calculateHeaderHeight();
        // Auto-size again after header height is calculated
        if (gridRef.current?.api) {
          gridRef.current.api.autoSizeAllColumns(false);
        }
      }, 250);
    }
  }, [calculateHeaderHeight]);

  // Handle first data rendered - set default sort
  const onFirstDataRendered = useCallback(() => {
    if (gridRef.current?.api) {
      // Set default sort by SHORTNAME ascending after data is rendered
      // Check if sort is already set to avoid resetting user's sort
      const currentSort = gridRef.current.api.getColumnState().find(col => col.colId === 'SHORTNAME' && col.sort);
      if (!currentSort) {
        gridRef.current.api.applyColumnState({
          state: [{ colId: 'SHORTNAME', sort: 'asc' }],
          defaultState: { sort: null }
        });
      }
    }
  }, []);

  // Preserve selection when data updates
  const prevBondsRef = useRef<BondListItem[]>([]);
  useEffect(() => {
    if (bonds.length > 0 && gridRef.current?.api) {
      // Check if data actually changed (not just a re-render)
      const dataChanged = 
        prevBondsRef.current.length !== bonds.length ||
        prevBondsRef.current.some((prevBond, index) => {
          const currentBond = bonds[index];
          return !currentBond || prevBond.SECID !== currentBond.SECID;
        });

      if (dataChanged && selectedBonds.size > 0) {
        // Restore selection after data update
        const timeoutId = setTimeout(() => {
          if (gridRef.current?.api) {
            // Restore selected rows by SECID
            selectedBonds.forEach((secid) => {
              const rowNode = gridRef.current?.api.getRowNode(secid);
              if (rowNode) {
                rowNode.setSelected(true, false); // false = don't clear other selections
              }
            });
          }
        }, 100);

        prevBondsRef.current = bonds;
        return () => clearTimeout(timeoutId);
      }
      
      prevBondsRef.current = bonds;
    }
  }, [bonds, selectedBonds]);

  // Recalculate header height and auto-size columns when data, columns, or window resize
  // Only auto-size on initial load or when columns actually change, not on portfolio updates
  useEffect(() => {
    if (bonds.length > 0 && gridRef.current?.api) {
      const timeoutId = setTimeout(() => {
        calculateHeaderHeight();
        // Only auto-size on initial load or major data changes, not on cell updates
        // This prevents table reformatting when portfolio changes
        if (bonds.length > 0 && prevBondsRef.current.length === 0) {
          gridRef.current?.api.autoSizeAllColumns(false);
        }
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [bonds.length, columnDefs, fieldDescriptions, calculateHeaderHeight]);


  // Recalculate on window resize
  useEffect(() => {
    const handleResize = () => {
      if (bonds.length > 0) {
        setTimeout(() => {
          calculateHeaderHeight();
        }, 100);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [bonds.length, calculateHeaderHeight]);

  // Refresh "Add to Portfolio" column cells when portfolio changes
  // Use suppressFlash to prevent visual flashing and layout shifts
  useEffect(() => {
    if (gridRef.current?.api && bonds.length > 0) {
      // Use requestAnimationFrame to batch updates and prevent layout thrashing
      requestAnimationFrame(() => {
        if (gridRef.current?.api) {
          gridRef.current.api.refreshCells({
            columns: ['addToPortfolio'],
            suppressFlash: true, // Prevent cell flashing animation
            force: false, // Use change detection instead of forcing refresh
          });
        }
      });
    }
  }, [portfolioBonds.length, bonds.length]);

  // Expose selected bonds via ref - MUST be before any conditional returns
  useImperativeHandle(ref, () => ({
    getSelectedBonds: () => {
      // Return a copy to prevent external mutations
      return new Set(selectedBonds);
    },
  }), [selectedBonds]);

  const handleExportSelected = async () => {
    if (selectedBonds.size === 0) {
      return;
    }

    try {
      await exportSelectedBonds(Array.from(selectedBonds));
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError('Не удалось экспортировать облигации');
      }
    }
  };

  const handleComparisonAnalysis = () => {
    if (selectedBonds.size === 0) {
      return;
    }
    // Force remount by updating key
    setComparisonDialogKey(prev => prev + 1);
    setIsComparisonDialogOpen(true);
  };

  // Get selected bonds data directly from AG Grid to avoid duplicates
  // This ensures we get the exact rows that are selected in the table (with current filter applied)
  const selectedBondsData = useMemo(() => {
    if (!gridRef.current?.api || selectedBonds.size === 0) return [];
    
    // Get selected rows directly from AG Grid (respects current filters)
    const selectedRows = gridRef.current.api.getSelectedRows() as BondListItem[];
    
    if (selectedRows.length === 0) return [];
    
    // Remove duplicates by SECID (in case AG Grid returns duplicates)
    const uniqueBonds = new Map<string, BondListItem>();
    selectedRows.forEach(bond => {
      if (bond && bond.SECID) {
        // Keep the bond with more complete data (prefer one with DURATION)
        const existing = uniqueBonds.get(bond.SECID);
        if (!existing) {
          uniqueBonds.set(bond.SECID, bond);
        } else if (bond.DURATION !== null && bond.DURATION !== undefined && 
                   (existing.DURATION === null || existing.DURATION === undefined)) {
          // Replace with bond that has DURATION data
          uniqueBonds.set(bond.SECID, bond);
        }
      }
    });
    
    return Array.from(uniqueBonds.values());
  }, [selectedBonds]); // Recalculate when selection changes

  // Check if component is closed
  if (isClosed) {
    return null;
  }

  // Loading state
  if (isLoading && bonds.length === 0) {
    return <LoadingSpinner message="Загрузка облигаций..." />;
  }

  // Error state
  if (error) {
    return <ErrorMessage message={error} onRetry={loadBonds} />;
  }

  // Filter bonds by search query
  const filteredBonds = useMemo(() => {
    if (!filters.search || filters.search.trim() === '') {
      return bonds;
    }
    
    const searchLower = filters.search.toLowerCase().trim();
    return bonds.filter(bond => {
      const secid = bond.SECID?.toLowerCase() || '';
      const shortname = bond.SHORTNAME?.toLowerCase() || '';
      return secid.includes(searchLower) || shortname.includes(searchLower);
    });
  }, [bonds, filters.search]);

  // Empty state
  if (bonds.length === 0) {
    return <EmptyState variant="no-results" />;
  }

  return (
    <Card sx={{ 
      position: isFullscreen ? 'fixed' : 'relative',
      top: isFullscreen ? 0 : 'auto',
      left: isFullscreen ? 0 : 'auto',
      width: isFullscreen ? '100vw' : '100%',
      height: isFullscreen ? '100vh' : '100%',
      zIndex: isFullscreen ? 2000 : 'auto',
      borderRadius: isFullscreen ? 0 : '6px',
      backgroundColor: '#ffffff',
      border: '1px solid #e0e0e0',
      boxShadow: isFullscreen ? '0 4px 10px rgba(0,0,0,0.15)' : '0 2px 4px rgba(0,0,0,0.06)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <CardContent sx={{ 
        p: 0, 
        flexGrow: 1, 
        display: 'flex', 
        flexDirection: 'column', 
        '&:last-child': { pb: 0 },
      }}>
        {/* Header with icon buttons */}
        <Box
          sx={{
            px: 1.5,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #e0e0e0',
            backgroundColor: '#fafafa',
            minHeight: '46px',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 'auto' }}>
            {/* Filter button */}
            {onOpenFilters && (
              <Tooltip title="Фильтры">
                <IconButton
                  size="small"
                  onClick={onOpenFilters}
                  sx={{ 
                    width: 28, 
                    height: 28,
                    padding: '4px',
                    '&:focus': {
                      outline: 'none',
                    },
                    '&:focus-visible': {
                      outline: 'none',
                    },
                  }}
                >
                  <FilterAltIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            {/* Comparison analysis button */}
            <Tooltip 
              title={
                selectedBonds.size === 0 
                  ? 'Выберите облигации для сравнения' 
                  : `Сравнительный анализ (${selectedBonds.size} облигаций)`
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={handleComparisonAnalysis}
                  disabled={selectedBonds.size === 0 || isLoading}
                  sx={{ 
                    width: 28, 
                    height: 28,
                    padding: '4px',
                    '&:focus': {
                      outline: 'none',
                    },
                    '&:focus-visible': {
                      outline: 'none',
                    },
                    '&.Mui-disabled': {
                      color: 'text.disabled',
                    },
                  }}
                >
                  <InsightsIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>

            {/* Export JSON button */}
            <Tooltip 
              title={
                selectedBonds.size === 0 
                  ? 'Выберите облигации для сохранения' 
                  : `Скачать JSON (${selectedBonds.size} облигаций)`
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={handleExportSelected}
                  disabled={selectedBonds.size === 0 || isLoading}
                  sx={{ 
                    width: 28, 
                    height: 28,
                    padding: '4px',
                    '&:focus': {
                      outline: 'none',
                    },
                    '&:focus-visible': {
                      outline: 'none',
                    },
                    '&.Mui-disabled': {
                      color: 'text.disabled',
                    },
                  }}
                >
                  <SaveIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>

            {/* Vertical divider */}
            <Box sx={{ width: '1px', backgroundColor: '#ddd', mx: 1 }} />

            {/* Refresh button */}
            <Tooltip title="Обновить данные">
              <IconButton
                size="small"
                onClick={() => triggerDataRefresh()}
                disabled={isLoading}
                sx={{ 
                  padding: '4px', 
                  width: 28, 
                  height: 28,
                  '&:focus': {
                    outline: 'none',
                  },
                  '&:focus-visible': {
                    outline: 'none',
                  },
                }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            
            {/* Fullscreen button */}
            <Tooltip title={isFullscreen ? 'Свернуть' : 'На весь экран'}>
              <IconButton
                size="small"
                onClick={() => setIsFullscreen(prev => !prev)}
                sx={{ 
                  padding: '4px', 
                  width: 28, 
                  height: 28,
                  '&:focus': {
                    outline: 'none',
                  },
                  '&:focus-visible': {
                    outline: 'none',
                  },
                }}
              >
                {isFullscreen ? <FullscreenExitIcon fontSize="small" /> : <FullscreenIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            
            {/* Close button */}
            <Tooltip title="Закрыть таблицу">
              <IconButton
                size="small"
                onClick={() => setIsClosed(true)}
                sx={{ 
                  padding: '4px', 
                  width: 28, 
                  height: 28,
                  '&:focus': {
                    outline: 'none',
                  },
                  '&:focus-visible': {
                    outline: 'none',
                  },
                }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Table content */}
        <Box sx={{ 
            flexGrow: 1, 
            display: 'flex', 
            height: '100%',
            width: '100%',
            overflow: 'hidden',
          }}>
        <Box
          className="ag-theme-material"
          sx={{
            height: '100%',
            width: '100%',
            flexGrow: 1,
            // Dynamic header height - use CSS variable if headerHeight is set
            ...(headerHeight && {
              '--ag-header-height': `${headerHeight}px`,
            }),
            // External border for table (Bootstrap .table-bordered style)
            '& .ag-root-wrapper': {
              border: '1px solid #dee2e6',
              borderRadius: '4px',
            },
            // Header cell: center content horizontally and vertically
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
            // Remove right border only from the last header cell in the main container
            '& .ag-header-cell:last-child': {
              borderRight: 'none !important',
            },
            '& .ag-center-cols-container ~ .ag-pinned-right-header .ag-header-cell:last-child': {
              borderRight: 'none !important',
            },
            // Ensure pinned-left header cells keep their right border
            '& .ag-pinned-left-header .ag-header-cell': {
              borderRight: '1px solid #dee2e6 !important',
            },
            // Label: only take space needed, allow text wrapping, remove all right spacing
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
            // Filter buttons: positioned immediately after label text, minimal gap
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
            // Remove any spacing between label and buttons
            '& .ag-header-cell-label + .ag-header-cell-menu-button': {
              marginLeft: '1px !important',
            },
            '& .ag-header-cell-label + .ag-header-cell-filter-button': {
              marginLeft: '1px !important',
            },
            // Ensure filter icons are always visible on the right
            '& .ag-header-cell-filtered .ag-header-cell-menu-button': {
              opacity: 1,
            },
            '& .ag-header-cell-filtered .ag-header-cell-filter-button': {
              opacity: 1,
            },
            // Unified font style for cells and headers
            '& .ag-cell, & .ag-header-cell': {
              fontFamily: 'Roboto, Helvetica, Arial, sans-serif',
              fontSize: '14px',
              lineHeight: 1.35,
            },
            '& .ag-cell': {
              // Bootstrap-style borders
              borderRight: '1px solid #dee2e6 !important',
              borderBottom: '1px solid #dee2e6 !important',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 12px !important',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxHeight: '38px !important',
              height: '38px !important',
              boxSizing: 'border-box',
              '& > *': {
                maxHeight: '38px !important',
                overflow: 'hidden',
              },
            },
            // Remove right border only from the last cell in the main container (not pinned-left/right)
            '& .ag-center-cols-container .ag-row .ag-cell:last-child': {
              borderRight: 'none !important',
            },
            '& .ag-pinned-right-cols-container .ag-row .ag-cell:last-child': {
              borderRight: 'none !important',
            },
            // Ensure pinned-left cells keep their right border (especially the last one before main content)
            '& .ag-pinned-left-cols-container .ag-cell': {
              borderRight: '1px solid #dee2e6 !important',
            },
            '& .ag-cell[col-id="SHORTNAME"]': {
              justifyContent: 'flex-start',
              textAlign: 'left !important',
            },
            // Ensure numeric columns are centered
            '& .ag-cell[col-id="PREVPRICE"], & .ag-cell[col-id="COUPON_YIELD_TO_PRICE"], & .ag-cell[col-id="YIELDATPREVWAPRICE"], & .ag-cell[col-id="FACEVALUE"], & .ag-cell[col-id="COUPONPERCENT"], & .ag-cell[col-id="COUPONPERCENT_NOMINAL"], & .ag-cell[col-id="COUPONPERIOD"], & .ag-cell[col-id="ACCRUEDINT"], & .ag-cell[col-id="DURATION_YEARS"], & .ag-cell[col-id="FACEUNIT"], & .ag-cell[col-id="RATING"]': {
              justifyContent: 'center',
              textAlign: 'center !important',
            },
            // Row styling - fixed height
            '& .ag-row': {
              cursor: 'pointer',
              minHeight: '38px !important',
              maxHeight: '38px !important',
              height: '38px !important',
              '& > *': {
                maxHeight: '38px !important',
              },
            },
            '& .ag-row-hover': {
              backgroundColor: '#f7f9fc !important',
            },
            // Prevent row click when clicking on portfolio action cell
            '& .ag-cell.portfolio-action-cell': {
              pointerEvents: 'auto',
              '& *': {
                pointerEvents: 'auto',
              },
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
          <AgGridReact<BondListItem>
            ref={gridRef}
            rowData={filteredBonds}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            onRowClicked={onRowClicked}
            onCellClicked={onCellClicked}
            onGridReady={onGridReady}
            onFirstDataRendered={onFirstDataRendered}
            rowSelection="multiple"
            onSelectionChanged={onSelectionChanged}
            animateRows={true}
            pagination={true}
            paginationPageSize={100}
            paginationPageSizeSelector={[50, 100, 200, 500]}
            enableCellTextSelection={true}
            suppressRowClickSelection={true}
            headerHeight={headerHeight}
            rowHeight={38}
            autoSizeStrategy={{
              type: 'fitGridWidth',
              defaultMinWidth: 80,
            }}
            suppressAggFuncInHeader={true}
            suppressMenuHide={true}
            getRowId={(params) => params.data.SECID}
          />
        </Box>
        </Box>
      </CardContent>
      <ComparisonAnalysisDialog
        key={comparisonDialogKey}
        open={isComparisonDialogOpen}
        onClose={() => setIsComparisonDialogOpen(false)}
        bonds={selectedBondsData}
      />
    </Card>
  );
});

BondsTable.displayName = 'BondsTable';

export default BondsTable;
