import React, { useEffect, useMemo, useCallback, useState, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, RowClickedEvent, CellClickedEvent, ICellRendererParams, IHeaderParams } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import '../bonds/ag-grid-tooltips.css';
import { Box, Card, CardContent, Button, Tooltip, IconButton, Alert } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import SaveIcon from '@mui/icons-material/Save';
import UploadFileIcon from '@mui/icons-material/UploadFile';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useUiStore } from '../../stores/uiStore';
import { useFiltersStore } from '../../stores/filtersStore';
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
import { PortfolioExportDialog } from './PortfolioExportDialog';
import { PortfolioImportDialog } from './PortfolioImportDialog';
import { exportPortfolio } from '../../utils/portfolioExport';

type FieldDescriptionMap = Record<string, string>;

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
 * PortfolioTable Component
 * 
 * Displays portfolio bonds using AG Grid with same columns as BondsTable
 * but without "Add to Portfolio" column and with "Remove from Portfolio" column
 */
export const PortfolioTable: React.FC = () => {
  const portfolioBonds = usePortfolioStore((state) => state.portfolioBonds);
  const removeBondFromPortfolio = usePortfolioStore((state) => state.removeBondFromPortfolio);
  const loadBondsToPortfolio = usePortfolioStore((state) => state.loadBondsToPortfolio);
  const clearPortfolio = usePortfolioStore((state) => state.clearPortfolio);
  const setSelectedBond = useUiStore((state) => state.setSelectedBond);
  const { filters } = useFiltersStore();
  const [fieldDescriptions, setFieldDescriptions] = useState<FieldDescriptionMap>({});
  const metadataLoadedRef = useRef(false);
  const gridRef = useRef<AgGridReact<BondListItem>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);
  const portfolioCellClickedRef = useRef(false);
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

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

  // Column definitions - same as BondsTable but without "Add to Portfolio" column
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
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            width: '100%',
            maxWidth: '100%',
          }}
        >
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {bond.SHORTNAME}
          </span>
          {hasCall && (
            <Box
              component="span"
              sx={{
                fontSize: '0.7em',
                fontWeight: 700,
                color: '#1976d2',
                ml: 1,
                whiteSpace: 'nowrap',
                flexShrink: 0,
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
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              PUT
            </Box>
          )}
        </Box>
      );
    };

    // Custom cell renderer for "Remove from Portfolio" column
    const RemoveFromPortfolioRenderer = (params: ICellRendererParams<BondListItem>) => {
      const bond = params.data;
      if (!bond) return null;

      const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent row click
        removeBondFromPortfolio(bond.SECID);
      };

      const handleCellClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent row click from opening details
        e.preventDefault(); // Prevent default behavior
      };

      const handleCellMouseDown = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent row click from opening details
        e.preventDefault(); // Prevent default behavior
      };

      return (
        <Box
          data-portfolio-cell
          onClick={handleCellClick}
          onMouseDown={handleCellMouseDown}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '32px',
            maxHeight: '32px',
            minHeight: '32px',
            cursor: 'default',
            padding: '0 !important',
            margin: '0 !important',
            lineHeight: '1',
          }}
        >
          <IconButton
            size="small"
            onClick={handleClick}
            sx={{
              color: 'error.main',
              padding: '4px !important',
              margin: '0 !important',
              width: '28px !important',
              height: '28px !important',
              minWidth: '28px !important',
              minHeight: '28px !important',
              maxWidth: '28px !important',
              maxHeight: '28px !important',
              '& .MuiSvgIcon-root': {
                fontSize: '18px !important',
              },
              '&:hover': {
                backgroundColor: 'error.light',
                color: 'error.contrastText',
              },
            }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      );
    };

    // Base column definition with common properties
    const createColumnDef = (field: string, headerName: string, otherProps: Partial<ColDef> = {}): ColDef => {
      const tooltipText = otherProps.headerTooltip !== undefined ? otherProps.headerTooltip : getFieldDescription(field);
      
      return {
        field,
        headerName,
        headerClass: 'ag-header-center',
        headerComponent: tooltipText ? CustomHeaderWithTooltip : undefined,
        headerTooltip: tooltipText,
        cellStyle: otherProps.cellStyle !== undefined ? otherProps.cellStyle : { textAlign: 'center' },
        ...otherProps,
      };
    };

    return [
    createColumnDef('SHORTNAME', 'Название', {
      minWidth: 120,
      pinned: 'left',
      cellRenderer: ShortNameRenderer,
      cellStyle: { textAlign: 'left' },
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
        return bond.RATING_LEVEL || null;
      },
      valueFormatter: (params) => {
        return params.value || '—';
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
        const couponFrequency = calculateCouponFrequency(bond.COUPONPERIOD);
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
        if (bond.DURATION === 0) return null;
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
      field: 'removeFromPortfolio',
      headerName: 'Удалить из портфеля',
      width: 150,
      minWidth: 150,
      maxWidth: 150,
      pinned: 'right',
      sortable: false,
      filter: false,
      suppressMenu: true,
      resizable: false, // Prevent column resizing to avoid layout shifts
      cellRenderer: RemoveFromPortfolioRenderer,
      cellStyle: { 
        textAlign: 'center', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        padding: '0 !important',
        height: '32px',
        maxHeight: '32px',
        minHeight: '32px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      },
      cellClass: 'portfolio-action-cell', // Add class for easier identification
      headerClass: 'ag-header-center',
      autoHeaderHeight: true,
      suppressSizeToFit: true, // Prevent auto-sizing to avoid layout shifts
    },
    ];
  }, [getFieldDescription, removeBondFromPortfolio]);

  // Default column properties
  const defaultColDef: ColDef = useMemo(() => ({
    sortable: true,
    filter: true,
    resizable: true,
    minWidth: 80,
    suppressSizeToFit: false,
    autoHeaderHeight: true,
    wrapText: false,
    autoHeight: false,
  }), []);

  // Handle cell click - intercept clicks on portfolio column
  const onCellClicked = useCallback((event: CellClickedEvent) => {
    // If clicking on "Remove from Portfolio" column, mark it and prevent row click
    if (event.column && event.column.getColId() === 'removeFromPortfolio') {
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
    
    // Check 2: Column object indicates portfolio column
    if (event.column?.getColId() === 'removeFromPortfolio') {
      return;
    }
    
    // Check 3: data-portfolio-cell attribute in click path
    if (target.closest('[data-portfolio-cell]')) {
      return;
    }
    
    // Check 4: Find the cell element that was clicked and check its col-id
    const clickedCell = target.closest('.ag-cell');
    if (clickedCell) {
      const colId = clickedCell.getAttribute('col-id');
      if (colId === 'removeFromPortfolio') {
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
        if (colId === 'removeFromPortfolio') {
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
        if (gridRef.current?.api) {
          gridRef.current.api.autoSizeAllColumns(false);
        }
      }, 250);
    }
  }, [calculateHeaderHeight]);

  // Handle first data rendered
  const onFirstDataRendered = useCallback(() => {
    if (gridRef.current?.api) {
      const currentSort = gridRef.current.api.getColumnState().find(col => col.colId === 'SHORTNAME' && col.sort);
      if (!currentSort) {
        gridRef.current.api.applyColumnState({
          state: [{ colId: 'SHORTNAME', sort: 'asc' }],
          defaultState: { sort: null }
        });
      }
      // Force reset row heights to ensure fixed height is applied
      setTimeout(() => {
        gridRef.current?.api.resetRowHeights();
      }, 100);
    }
  }, []);

  // Recalculate header height when data changes
  useEffect(() => {
    if (portfolioBonds.length > 0 && gridRef.current?.api) {
      const timeoutId = setTimeout(() => {
        calculateHeaderHeight();
        gridRef.current?.api.autoSizeAllColumns(false);
        // Force reset row heights to ensure fixed height is applied
        gridRef.current?.api.resetRowHeights();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [portfolioBonds.length, columnDefs, fieldDescriptions, calculateHeaderHeight]);

  // Recalculate on window resize
  useEffect(() => {
    const handleResize = () => {
      if (portfolioBonds.length > 0) {
        setTimeout(() => {
          calculateHeaderHeight();
        }, 100);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [portfolioBonds.length, calculateHeaderHeight]);

  const handleExportPortfolio = async (format: 'full' | 'secid-only') => {
    try {
      setExportError(null);
      await exportPortfolio(portfolioBonds, format);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Не удалось сохранить портфель';
      setExportError(errorMessage);
      console.error('Failed to export portfolio:', error);
    }
  };

  const handleImportPortfolio = (bonds: BondListItem[]) => {
    loadBondsToPortfolio(bonds);
  };

  const handleClearPortfolio = () => {
    if (window.confirm('Вы уверены, что хотите удалить все облигации из портфеля?')) {
      clearPortfolio();
    }
  };

  // Filter portfolio bonds by search query
  const filteredPortfolioBonds = useMemo(() => {
    if (!filters.search || filters.search.trim() === '') {
      return portfolioBonds;
    }
    
    const searchLower = filters.search.toLowerCase().trim();
    return portfolioBonds.filter(bond => {
      const secid = bond.SECID?.toLowerCase() || '';
      const shortname = bond.SHORTNAME?.toLowerCase() || '';
      return secid.includes(searchLower) || shortname.includes(searchLower);
    });
  }, [portfolioBonds, filters.search]);

  // Empty state
  if (portfolioBonds.length === 0) {
    return (
      <Box sx={{ flexGrow: 1, minHeight: 0, width: '100%' }}>
        <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', width: '100%' }}>
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
                Загрузить портфель
              </Button>
            </Box>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <EmptyState
                title="Портфель пуст"
                message="Добавьте облигации в портфель из вкладки 'Скринер облигаций', нажав на иконку плюса в столбце 'Добавить в портфель', или загрузите портфель из файла."
              />
            </Box>
          </CardContent>
          <PortfolioImportDialog
            open={isImportDialogOpen}
            onClose={() => setIsImportDialogOpen(false)}
            onImport={handleImportPortfolio}
          />
        </Card>
      </Box>
    );
  }

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', width: '100%' }}>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
        {exportError && (
          <Alert severity="error" onClose={() => setExportError(null)} sx={{ m: 1 }}>
            {exportError}
          </Alert>
        )}
        <Box sx={{ p: 1, display: 'flex', justifyContent: 'space-between', gap: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<SaveIcon />}
              onClick={() => setIsExportDialogOpen(true)}
              disabled={portfolioBonds.length === 0}
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabledBackground',
                },
              }}
            >
              Сохранить портфель
            </Button>
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
              Загрузить портфель
            </Button>
            <Button
              variant="outlined"
              size="small"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleClearPortfolio}
              disabled={portfolioBonds.length === 0}
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabledBackground',
                },
              }}
            >
              Очистить портфель
            </Button>
          </Box>
        </Box>
        <Box sx={{ flexGrow: 1, display: 'flex' }}>
        <Box
          className="ag-theme-material"
          sx={{
            height: '100%',
            width: '100%',
            ...(headerHeight && {
              '--ag-header-height': `${headerHeight}px`,
            }),
            '& .ag-header-cell': {
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 4px',
              boxSizing: 'border-box',
              gap: '0px !important',
              borderRight: '1px solid rgba(224, 224, 224, 0.8)',
              '&:last-child': {
                borderRight: 'none',
              },
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
              borderRight: '1px solid rgba(224, 224, 224, 0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: '1.5 !important',
              padding: '4px 4px !important',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap !important',
              maxHeight: '32px !important',
              height: '32px !important',
              minHeight: '32px !important',
              boxSizing: 'border-box',
              '&:last-child': {
                borderRight: 'none',
              },
              '& > *': {
                maxHeight: '24px !important',
                overflow: 'hidden',
                whiteSpace: 'nowrap !important',
              },
            },
            '& .ag-cell[col-id="SHORTNAME"]': {
              justifyContent: 'flex-start',
              whiteSpace: 'nowrap !important',
              '& > *': {
                whiteSpace: 'nowrap !important',
              },
            },
            '& .ag-cell[col-id="removeFromPortfolio"]': {
              padding: '0 !important',
              height: '32px !important',
              maxHeight: '32px !important',
              minHeight: '32px !important',
            },
            '& .ag-row': {
              cursor: 'pointer',
              minHeight: '32px !important',
              maxHeight: '32px !important',
              height: '32px !important',
              '& > *': {
                maxHeight: '32px !important',
              },
            },
            '& .ag-cell-wrapper': {
              whiteSpace: 'nowrap !important',
              overflow: 'hidden !important',
            },
            '& .ag-cell-value': {
              whiteSpace: 'nowrap !important',
              overflow: 'hidden !important',
            },
            '& .ag-row-hover': {
              backgroundColor: 'rgba(25, 118, 210, 0.04)',
            },
            // Prevent row click when clicking on portfolio action cell
            '& .ag-cell.portfolio-action-cell': {
              pointerEvents: 'auto',
              padding: '0 !important',
              height: '32px !important',
              maxHeight: '32px !important',
              minHeight: '32px !important',
              '& *': {
                pointerEvents: 'auto',
                maxHeight: '32px !important',
              },
            },
            // Center header class
            '& .ag-header-center .ag-header-cell-label': {
              justifyContent: 'center',
            },
          }}
        >
          <AgGridReact<BondListItem>
            ref={gridRef}
            rowData={filteredPortfolioBonds}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            onRowClicked={onRowClicked}
            onCellClicked={onCellClicked}
            onGridReady={onGridReady}
            onFirstDataRendered={onFirstDataRendered}
            animateRows={true}
            pagination={true}
            paginationPageSize={100}
            paginationPageSizeSelector={[50, 100, 200, 500]}
            enableCellTextSelection={true}
            suppressRowClickSelection={true}
            headerHeight={headerHeight}
            rowHeight={32}
            suppressRowAutoHeight={true}
            autoSizeStrategy={{
              type: 'fitGridWidth',
              defaultMinWidth: 80,
            }}
            suppressAggFuncInHeader={true}
            suppressMenuHide={true}
            getRowId={(params) => params.data.SECID}
            suppressHeaderTooltips={true}
          />
        </Box>
        </Box>
      </CardContent>
      <PortfolioExportDialog
        open={isExportDialogOpen}
        onClose={() => setIsExportDialogOpen(false)}
        onConfirm={handleExportPortfolio}
        bondCount={portfolioBonds.length}
      />
      <PortfolioImportDialog
        open={isImportDialogOpen}
        onClose={() => setIsImportDialogOpen(false)}
        onImport={handleImportPortfolio}
      />
    </Card>
  );
};
