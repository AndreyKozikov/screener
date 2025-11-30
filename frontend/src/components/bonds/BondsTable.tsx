import React, { useEffect, useMemo, useCallback, useState, useRef, useImperativeHandle } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, RowClickedEvent, ICellRendererParams, IHeaderParams } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import './ag-grid-tooltips.css';
import { Box, Card, CardContent, Button, Tooltip } from '@mui/material';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);
import { useBondsStore } from '../../stores/bondsStore';
import { useFiltersStore } from '../../stores/filtersStore';
import { useUiStore } from '../../stores/uiStore';
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

type FieldDescriptionMap = Record<string, string>;

// Export selected bonds for use in parent component
export type BondsTableRef = {
  getSelectedBonds: () => Set<string>;
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
 * BondsTable Component
 * 
 * Main data table displaying bonds using AG Grid
 */
export const BondsTable = React.forwardRef<BondsTableRef, {}>((_props, ref) => {
  const { bonds, isLoading, error, setBonds, setLoading, setError } = useBondsStore();
  const { filters } = useFiltersStore();
  const setSelectedBond = useUiStore((state) => state.setSelectedBond);
  const dataRefreshVersion = useUiStore((state) => state.dataRefreshVersion);
  const [fieldDescriptions, setFieldDescriptions] = useState<FieldDescriptionMap>({});
  const metadataLoadedRef = useRef(false);
  const gridRef = useRef<AgGridReact<BondListItem>>(null);
  const [headerHeight, setHeaderHeight] = useState<number | undefined>(undefined);
  const [selectedBonds, setSelectedBonds] = useState<Set<string>>(new Set());
  const [isComparisonDialogOpen, setIsComparisonDialogOpen] = useState(false);
  const [comparisonDialogKey, setComparisonDialogKey] = useState(0);

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
            alignItems: 'baseline',
            gap: 0.5,
          }}
        >
          <span>{bond.SHORTNAME}</span>
          {hasCall && (
            <Box
              component="sup"
              sx={{
                fontSize: '0.7em',
                fontWeight: 600,
                color: 'primary.main',
                lineHeight: 1,
              }}
            >
              CALL
            </Box>
          )}
          {hasPut && (
            <Box
              component="sup"
              sx={{
                fontSize: '0.7em',
                fontWeight: 600,
                color: 'secondary.main',
                lineHeight: 1,
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
      
      return {
        field,
        headerName,
        headerClass: 'ag-header-center',
        // Используем кастомный header component с Material-UI Tooltip
        headerComponent: tooltipText ? CustomHeaderWithTooltip : undefined,
        headerTooltip: tooltipText, // Оставляем для совместимости
        // Center align cell content by default (can be overridden in otherProps)
        cellStyle: otherProps.cellStyle !== undefined ? otherProps.cellStyle : { textAlign: 'center' },
        ...otherProps,
      };
    };

    return [
    {
      field: 'checkbox',
      headerName: '',
      checkboxSelection: true,
      headerCheckboxSelection: true,
      width: 50,
      pinned: 'left',
      sortable: false,
      filter: false,
      suppressMenu: true,
      cellStyle: { textAlign: 'center' },
    },
    createColumnDef('SHORTNAME', 'Название', {
      minWidth: 120,
      pinned: 'left',
      cellRenderer: ShortNameRenderer,
      cellStyle: { textAlign: 'left' }, // Left align for name column
      headerTooltip: getFieldDescription('SHORTNAME'),
      autoHeaderHeight: true,
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
        return calculateCouponYieldToPrice(bond.COUPONPERCENT, bond.PREVPRICE);
      },
      valueFormatter: (params) => formatPercent(params.value),
      type: 'numericColumn',
      headerTooltip: getFieldDescription('COUPON_YIELD_TO_PRICE') || getFieldDescription('COUPONPERCENT'),
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

  // Handle row click - don't interfere with checkbox selection
  const onRowClicked = useCallback((event: RowClickedEvent) => {
    // Only open details, don't change checkbox selection
    // Checkbox selection is handled separately by AG Grid
    if (event.event && (event.event.target as HTMLElement).closest('.ag-checkbox')) {
      // If clicking on checkbox, let AG Grid handle it
      return;
    }
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
  useEffect(() => {
    if (bonds.length > 0 && gridRef.current?.api) {
      const timeoutId = setTimeout(() => {
        calculateHeaderHeight();
        // Auto-size all columns to fit content after data is loaded
        gridRef.current?.api.autoSizeAllColumns(false);
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

  // Loading state
  if (isLoading && bonds.length === 0) {
    return <LoadingSpinner message="Загрузка облигаций..." />;
  }

  // Error state
  if (error) {
    return <ErrorMessage message={error} onRetry={loadBonds} />;
  }

  // Empty state
  if (bonds.length === 0) {
    return <EmptyState variant="no-results" />;
  }

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 }, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-end', gap: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Button
            variant="outlined"
            size="small"
            onClick={handleComparisonAnalysis}
            disabled={selectedBonds.size === 0 || isLoading}
            sx={{
              '&.Mui-disabled': {
                color: 'text.disabled',
                borderColor: 'action.disabledBackground',
              },
            }}
          >
            Сравнительный анализ{selectedBonds.size > 0 && ` (${selectedBonds.size})`}
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleExportSelected}
            disabled={selectedBonds.size === 0 || isLoading}
            sx={{
              '&.Mui-disabled': {
                color: 'text.disabled',
                borderColor: 'action.disabledBackground',
              },
            }}
          >
            Скачать JSON{selectedBonds.size > 0 && ` (${selectedBonds.size})`}
          </Button>
        </Box>
        <Box sx={{ flexGrow: 1, display: 'flex' }}>
        <Box
          className="ag-theme-material"
          sx={{
            height: '100%',
            width: '100%',
            // Dynamic header height - use CSS variable if headerHeight is set
            ...(headerHeight && {
              '--ag-header-height': `${headerHeight}px`,
            }),
            // Header cell: center content horizontally and vertically
            '& .ag-header-cell': {
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 4px',
              boxSizing: 'border-box',
              gap: '0px !important',
              // Vertical separators - add borders between columns
              borderRight: '1px solid rgba(224, 224, 224, 0.8)',
              '&:last-child': {
                borderRight: 'none',
              },
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
            '& .ag-cell': {
              borderRight: '1px solid rgba(224, 224, 224, 0.8)',
              '&:last-child': {
                borderRight: 'none',
              },
            },
            // Row styling - keep body rows unchanged (fixed height)
            '& .ag-row': {
              cursor: 'pointer',
            },
            '& .ag-row-hover': {
              backgroundColor: 'rgba(25, 118, 210, 0.04)',
            },
            // Center header class
            '& .ag-header-center .ag-header-cell-label': {
              justifyContent: 'center',
            },
          }}
        >
          <AgGridReact<BondListItem>
            ref={gridRef}
            rowData={bonds}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            onRowClicked={onRowClicked}
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
            autoSizeStrategy={{
              type: 'fitGridWidth',
              defaultMinWidth: 80,
            }}
            suppressAggFuncInHeader={true}
            suppressMenuHide={true}
            getRowId={(params) => params.data.SECID}
            // Отключаем встроенные tooltips AG Grid, используем Material-UI Tooltip
            suppressHeaderTooltips={true}
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
