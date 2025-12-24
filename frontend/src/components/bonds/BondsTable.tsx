import React, { useEffect, useMemo, useCallback, useState, useRef } from 'react';
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
import AddToPortfolioRenderer from './AddToPortfolioRenderer';
import AddToComparisonRenderer from './AddToComparisonRenderer';

type FieldDescriptionMap = Record<string, string>;

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
export const BondsTable: React.FC<BondsTableProps> = ({ onOpenFilters }) => {
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

  // Portfolio icon SVG component
  const PortfolioIcon = React.memo(() => (
    <svg
      clipRule="evenodd"
      fillRule="evenodd"
      imageRendering="optimizeQuality"
      shapeRendering="geometricPrecision"
      textRendering="geometricPrecision"
      viewBox="0 0 1706.66 1706.66"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        width: '1.5rem',
        height: '1.5rem',
      }}
    >
      <g id="Layer_x0020_1">
        <path d="m986.39 738.99c-24.07 0-27.37-35.39-3.53-39.68l261.5-47.12c25.8-4.7 33.07 34.69 7.09 39.36l-265.07 47.44zm-266.38-.81-264.26-46.51c-25.88-4.59-19.02-44.04 6.97-39.39l260.75 46.21c23.88 4.24 20.68 39.69-3.46 39.69zm-419.34-74.33-222.65-39.09c-9.54-1.7-16.5-9.97-16.52-19.67l-.29-222.97c-.12-91.43 74.57-166.01 165.98-166.01h1252.3c91.39 0 166.02 74.58 165.98 165.98l-.1 221.76c-.02 9.68-6.94 17.96-16.47 19.68l-219.69 39.59c-25.88 4.64-33.02-34.7-7.08-39.36l203.24-36.63.08-205.05c.03-69.31-56.68-125.97-125.97-125.97h-1252.29c-69.28 0-126.07 56.63-125.98 125.94l.26 206.22 202.66 35.87c23.92 4.24 20.64 39.71-3.46 39.71z"/>
        <path d="m1436.12 1419.46h-295.57c-26.33 0-26.32-40 0-40h295.57c69.47 0 125.97-56.5 125.97-125.97v-641c0-26.32 40-26.32 40 0v640.98c.02 91.53-74.44 166-165.97 166zm-870 0h-295.59c-91.52 0-165.98-74.46-165.98-165.98v-640.99c0-26.33 40-26.33 40 0v640.98c0 69.47 56.52 125.97 125.98 125.97h295.59c26.34 0 26.31 40.03 0 40.03z"/>
        <path d="m853.32 897.53c-85.53 0-155.11-69.59-155.11-155.12 0-85.52 69.58-155.13 155.11-155.13s155.12 69.59 155.12 155.11c0 85.53-69.59 155.14-155.12 155.14zm0-270.25c-63.47 0-115.12 51.64-115.12 115.12s51.65 115.11 115.12 115.11 115.11-51.63 115.11-115.12c0-63.48-51.64-115.11-115.11-115.11z"/>
        <path d="m397.5 1069.59h-34.75c-45.1 0-81.78-36.69-81.78-81.78v-751.68c0-26.33 40-26.33 40 0v751.69c0 47.72 50.8 41.77 76.53 41.77 23.03 0 41.76-18.73 41.76-41.76v-751.7c0-26.33 40-26.33 40 0v751.69c0 45.09-36.68 81.77-81.76 81.77z"/>
        <path d="m507.41 973.53c-31.42 0-68.11 6.9-68.11-20 0-37.33 72.07-9.51 72.07-23.96v-152.82c0-2.15-1.81-3.97-3.96-3.97h-254.59c-2.15 0-3.98 1.82-3.98 3.97v152.8c0 14.45 72.16-13.38 72.16 23.96 0 26.91-36.72 20-68.18 20-24.25 0-43.97-19.74-43.97-43.97v-152.79c0-24.25 19.72-43.97 43.97-43.97h254.59c24.24 0 43.96 19.72 43.96 43.97v152.8c0 24.24-19.72 43.97-43.96 43.97z"/>
        <path d="m380.12 829.91c-11.04 0-20-8.96-20-20v-96.51c0-26.33 40-26.33 40 0v96.51c0 11.04-8.96 20-20 20z"/>
        <path d="m1343.9 1069.59h-34.75c-45.08 0-81.78-36.69-81.78-81.78v-751.68c0-26.33 40-26.33 40 0v751.69c0 47.72 50.79 41.77 76.51 41.77 23.03 0 41.76-18.73 41.76-41.76v-751.7c0-26.33 40-26.33 40 0v751.69c.03 45.09-36.67 81.77-81.75 81.77z"/>
        <path d="m1453.81 973.53c-31.42 0-68.11 6.9-68.11-20 0-37.32 72.07-9.51 72.07-23.96v-152.82c0-2.15-1.81-3.97-3.96-3.97h-254.58c-2.15 0-3.96 1.82-3.96 3.97v152.8c0 14.46 72.14-13.38 72.14 23.96 0 26.91-36.74 20-68.19 20-24.24 0-43.97-19.74-43.97-43.97v-152.79c0-24.25 19.74-43.97 43.97-43.97h254.58c24.24 0 43.97 19.72 43.97 43.97v152.8c0 24.24-19.74 43.97-43.97 43.97z"/>
        <path d="m1326.52 829.91c-11.04 0-20-8.96-20-20v-96.51c0-26.33 40-26.33 40 0v96.51c.02 11.04-8.96 20-20 20z"/>
        <path d="m1167.1 256.13c-11.04 0-20-8.96-20-20 0-155.14 14.28-148.41-105.47-148.41-26.33 0-26.32-40 0-40h63.71c45.08 0 81.78 36.68 81.78 81.76v106.65c-.02 11.04-8.98 20-20.02 20zm-627.55-.26c-11.04 0-20-8.96-20-20v-106.39c0-45.08 36.68-81.76 81.76-81.76 40.68 0 83.69-8.26 83.69 20s-43.02 20-83.69 20c-23.03 0-41.76 18.74-41.76 41.76v106.39c0 11.04-8.94 20-20 20z"/>
        <path d="m1012.85 134.61h-319.05c-54.83 0-48.78-57.25-48.78-85.83 0-26.9 21.87-48.78 48.78-48.78h319.06c54.81 0 48.79 57.21 48.78 85.83-.02 26.91-21.89 48.78-48.8 48.78zm-319.05-94.59c-13.11 0-8.78 23.5-8.78 45.83 0 4.75 4.03 8.78 8.78 8.78h319.06c13.09 0 8.77-23.5 8.77-45.83 0-4.75-4.02-8.78-8.77-8.78z"/>
        <path d="m853.32 1706.66c-169.4 0-307.2-137.83-307.2-307.23 0-169.39 137.8-307.2 307.2-307.2s307.22 137.82 307.22 307.2c0 169.41-137.82 307.23-307.22 307.23zm0-574.42c-147.33 0-267.2 119.86-267.2 267.19 0 147.35 119.87 267.22 267.2 267.22s267.2-119.87 267.2-267.22c0-147.33-119.87-267.19-267.2-267.19z"/>
        <path d="m853.32 1572.65c-88.87 0-122.28-116.61-76.61-116.61 11.04 0 20 8.97 20 20 0 74.47 113.19 74.51 113.19 0 0-40.75-19.87-47.29-61.22-57.14-38.8-9.23-91.97-21.89-91.97-96.06 0-53.26 43.33-96.61 96.61-96.61 88.87 0 122.26 116.61 76.59 116.61-11.03 0-20-8.97-20-20 0-74.51-113.19-74.47-113.19 0 0 40.77 19.87 47.29 61.23 57.14 38.8 9.25 91.97 21.9 91.97 96.06-.01 53.27-43.34 96.61-96.61 96.61z"/>
        <path d="m853.32 1266.24c-25.23 0-20-30.63-20-51.82 0-26.33 40-26.32 40 0 0 21.21 5.23 51.82-20 51.82z"/>
        <path d="m853.32 1604.46c-25.23 0-20-30.63-20-51.82 0-26.33 40-26.32 40 0 0 21.2 5.23 51.82-20 51.82z"/>
        <path d="m439.26 732.78v-476.67h-118.29v476.67h39.15v-19.39c0-26.33 40-26.33 40 0v19.39z" fill="#ffd08c"/>
        <path d="m1267.37 256.11v476.67h39.15v-19.39c0-26.33 40-26.33 40 0v19.39h39.12v-476.67z" fill="#ffd08c"/>
        <path d="m1306.52 772.78h-39.15v215.04c0 47.72 50.79 41.77 76.51 41.77 23.03 0 41.76-18.73 41.76-41.76v-215.04h-39.12c0 24.61 5.82 57.12-20 57.12s-20-32.56-20-57.12z" fill="#ffd08c"/>
        <g fill="#c35e49">
          <path d="m1227.37 933.11v-160.32c-13.97 0-32.09-2.66-32.09 3.97v152.8c0 6.7 15.48 4.32 32.09 3.55z"/>
          <path d="m1425.65 772.78v160.33c16.63.77 32.13 3.16 32.13-3.54v-152.82c0-6.63-18.16-3.97-32.13-3.97z"/>
          <path d="m511.37 929.57v-152.82c0-6.63-18.14-3.97-32.11-3.97v160.33c16.62.77 32.11 3.15 32.11-3.54z"/>
          <path d="m280.97 933.1v-160.32c-13.91 0-32.13-2.66-32.13 3.97v152.8c0 6.7 15.5 4.31 32.13 3.54z"/>
        </g>
        <path d="m738.2 742.41c0 63.48 51.65 115.11 115.12 115.11s115.11-51.63 115.11-115.12c0-63.48-51.64-115.11-115.11-115.11s-115.12 51.64-115.12 115.12z" fill="#ffd08c"/>
        <path d="m705.52 695.31c45.89-143.65 250.61-143.22 295.83.67l226.02-40.73v-399.14h-748.11v399.1z" fill="#d06751"/>
        <path d="m693.8 94.63h319.06c13.17 0 8.77-30.23 8.77-45.83 0-4.75-4.02-8.78-8.77-8.78h-319.06c-12.8 0-8.78 29.78-8.78 45.83 0 4.75 4.03 8.78 8.78 8.78z" fill="#ffd08c"/>
        <path d="m1227.37 695.86-219.09 39.21c4.03 88.62-66.7 162.46-154.95 162.46-88.66 0-159.5-74.59-154.91-163.15l-219.16-38.57v36.97h28.15c24.24 0 43.96 19.72 43.96 43.97v152.8c0 24.24-19.72 43.97-43.96 43.97-9.28 0-19.03.6-28.15.76v13.53c0 45.09-36.68 81.77-81.76 81.77h-34.75c-45.1 0-81.78-36.69-81.78-81.78v-13.53c-9.12-.16-18.87-.76-28.15-.76-24.25 0-43.97-19.74-43.97-43.97v-152.79c0-24.25 19.72-43.97 43.97-43.97h28.15v-72.39l-136.43-23.96v617.02c0 69.47 56.52 125.97 125.98 125.97h276.24c10.33-160.11 143.88-287.2 306.56-287.2 162.69 0 296.25 127.12 306.57 287.23h276.22c69.47 0 125.97-56.5 125.97-125.97v-617.91l-136.44 24.59v72.63h28.17c24.24 0 43.97 19.72 43.97 43.97v152.8c0 24.24-19.74 43.97-43.97 43.97-9.29 0-19.04.6-28.17.76v13.53c.03 45.09-36.67 81.77-81.75 81.77h-34.75c-45.08 0-81.78-36.69-81.78-81.78v-13.53c-9.12-.16-18.86-.76-28.14-.76-24.24 0-43.97-19.74-43.97-43.97v-152.79c0-24.25 19.74-43.97 43.97-43.97h28.14v-36.92z" fill="#d9745e"/>
        <path d="m1120.53 1399.43c0-147.33-119.87-267.19-267.2-267.19s-267.2 119.86-267.2 267.19c0 147.35 119.87 267.22 267.2 267.22s267.2-119.87 267.2-267.22zm-210.61-76.59c0-74.51-113.19-74.47-113.19 0 0 40.77 19.87 47.29 61.23 57.14 38.8 9.25 91.97 21.9 91.97 96.06-.01 46.26-32.69 85.03-76.17 94.43.22 17.28-1.79 34-20.43 34-18.63 0-20.65-16.7-20.43-33.98-73.32-15.92-98.16-114.45-56.17-114.45 11.04 0 20 8.97 20 20 0 74.47 113.19 74.51 113.19 0 0-40.75-19.87-47.29-61.22-57.14-38.8-9.23-91.97-21.89-91.97-96.06 0-46.29 32.72-85.08 76.26-94.45.13-4.83.35-9.61.35-13.98 0-26.33 40-26.32 40 0 0 4.37.22 9.15.35 13.96 73.37 15.87 98.23 114.46 56.24 114.46-11.03 0-20-8.97-20-20z" fill="#ff9621"/>
        <path d="m1425.65 256.11v363.41l179.71-32.39.08-205.05c.03-69.31-56.68-125.97-125.97-125.97h-53.83z" fill="#d06751"/>
        <path d="m280.97 620.05v-363.93h-53.79c-69.28 0-126.07 56.63-125.98 125.94l.26 206.22 179.51 31.78z" fill="#d06751"/>
        <path d="m380.12 829.91c-25.82 0-20-32.56-20-57.12h-39.15v215.04c0 47.72 50.8 41.77 76.53 41.77 23.03 0 41.76-18.73 41.76-41.76v-215.04h-39.14c0 24.57 5.82 57.12-20 57.12z" fill="#ffd08c"/>
      </g>
    </svg>
  ));

  PortfolioIcon.displayName = 'PortfolioIcon';

  // Comparison icon SVG component
  const ComparisonIcon = React.memo(() => (
    <svg
      clipRule="evenodd"
      fillRule="evenodd"
      imageRendering="optimizeQuality"
      shapeRendering="geometricPrecision"
      textRendering="geometricPrecision"
      viewBox="0 0 1706.66 1706.66"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        width: '1.5rem',
        height: '1.5rem',
      }}
    >
      <g id="Layer_x0020_1">
        <path d="m749.3 485.57c-36.26 0-10.95-50.79-2.89-75.35l-66.61 14.58c-25.72 5.6-34.29-33.43-8.56-39.09l100.79-22.07c15.06-3.31 28.09 11.11 23.28 25.76l-27.02 82.37c-2.76 8.43-10.59 13.79-19 13.79z"/>
        <path d="m366.11 522.97c-21.19 0-27.79-29-8.54-38.09l139.79-65.96c5.4-2.56 11.65-2.56 17.07 0l118.26 55.81 130.97-107.04c20.33-16.59 45.61 14.39 25.3 30.97l-140.74 115.01c-5.97 4.89-14.21 5.89-21.19 2.6l-121.14-57.17c-18.07 8.52-129.96 63.87-139.78 63.87z"/>
        <path d="m795.85 791.65c-11.04 0-20-8.96-20-20v-226.26c0-26.33 40-26.33 40 0v226.26c0 11.04-8.96 20-20 20z"/>
        <path d="m641.03 791.65c-11.04 0-20-8.96-20-20v-173c0-26.33 40-26.33 40 0v173c0 11.04-8.96 20-20 20z"/>
        <path d="m486.22 791.65c-11.04 0-20-8.96-20-20v-226.26c0-26.33 40-26.33 40 0v226.26c0 11.04-8.96 20-20 20z"/>
        <path d="m331.4 791.65c-11.04 0-20-8.96-20-20v-173c0-26.33 40-26.33 40 0v173c0 11.04-8.95 20-20 20z"/>
        <path d="m911.34 791.65h-699.99c-11.04 0-20-8.96-20-20v-420.3c0-26.33 40-26.33 40 0v400.3h679.99c26.33 0 26.33 40 0 40z"/>
        <path d="m561.34 1122.82c-498.79 0-749.69-605.48-396.93-958.25 352.71-352.73 958.26-101.92 958.26 396.93 0 310.19-251.14 561.32-561.33 561.32zm0-1082.67c-463.3 0-696.21 562.4-368.63 889.97 327.65 327.65 889.98 94.57 889.98-368.63 0-288.09-233.26-521.34-521.34-521.34z"/>
        <path d="m963.24 1116.48c-5.11 0-10.24-1.96-14.15-5.86l-91.43-91.43c-18.64-18.64 9.69-46.92 28.3-28.29l91.44 91.43c12.63 12.65 3.51 34.16-14.15 34.16zm133.08-133.08c-5.11 0-10.24-1.96-14.15-5.87l-91.43-91.44c-18.63-18.63 9.69-46.9 28.3-28.29l91.43 91.43c12.64 12.64 3.51 34.17-14.14 34.17z"/>
        <path d="m1503.94 1706.49c-11.93 0-23.72-4.92-32.3-13.51l-534.81-534.81c-17.26-17.29-18.28-45.29-1.21-62.33l160.39-160.4c16.15-16.17 45.51-15.57 62.33 1.22l534.81 534.83c17.51 17.5 18.09 45.46 1.24 62.32l-160.4 160.41c-7.92 7.9-18.58 12.28-30.04 12.28zm-377.91-743.33-162.7 162.87c.22 4.92 489.46 491.4 536.6 538.66 2.93 2.94 4.74 2.25 5.76 1.23l160.4-160.4c.89-.89.88-3.65-1.22-5.75-47.49-47.43-532.85-536.61-538.83-536.61z"/>
        <path d="m1527.52 1591.94c-84.5 0-84.49-128.51-.01-128.51 84.5 0 84.52 128.51.01 128.51zm0-88.52c-21.52 0-32.39 26.19-17.15 41.44 22.13 22.15 57.26-11.37 34.32-34.33-4.59-4.6-10.69-7.11-17.17-7.11z"/>
        <path d="m1358.73 1571.77c-17.64 0-26.81-21.51-14.15-34.16l193.22-193.2c18.65-18.65 46.91 9.7 28.3 28.3l-193.22 193.2c-3.91 3.92-9.03 5.86-14.14 5.86z"/>
        <path d="m1001.5 1214.56c-17.64 0-26.81-21.51-14.15-34.16l193.2-193.2c18.65-18.65 46.91 9.7 28.3 28.3l-193.2 193.2c-3.91 3.91-9.03 5.86-14.14 5.86z"/>
        <g fill="#015c55">
          <path d="m1527.52 1463.43c84.5 0 84.52 128.51.01 128.51-84.5 0-84.49-128.51-.01-128.51zm24.69-76.84-165.35 165.34c57.15 56.97 100.59 100.24 113.07 112.75 2.93 2.94 4.74 2.25 5.76 1.23l160.4-160.4c.89-.89.88-3.65-1.22-5.75-12.56-12.55-55.78-56.02-112.66-113.17z"/>
          <path d="m1358.52 1523.68 165.46-165.45c-106.5-106.98-246.58-247.47-329-328.87l-165.25 165.25c81.46 82.3 221.89 222.49 328.79 329.07z"/>
          <path d="m1001.62 1166.13 164.83-164.83c-24.4-23.89-39.39-38.14-40.42-38.14l-162.7 162.87c.04.84 14.35 15.74 38.3 40.1z"/>
        </g>
        <path d="m963.26 1068.19 104.78-104.79-60.77-60.78c-30.16 39.38-65.42 74.63-104.79 104.79l60.78 60.77z" fill="#014b45"/>
        <path d="m192.71 930.13c243.87 243.87 617.75 177.11 793-63.98 1.32-3.76 3.76-7.15 6.87-9.69 56.12-81.14 90.1-181.1 90.1-294.96 0-288.09-233.26-521.34-521.34-521.34-463.3 0-696.21 562.4-368.63 889.97zm718.63-178.48c26.33 0 26.33 40 0 40h-115.48-154.82-154.81-154.82-120.05c-11.04 0-20-8.96-20-20v-420.3c0-26.33 40-26.33 40 0v400.3h80.05v-153c0-26.33 40-26.33 40 0v153h114.82v-206.26c0-26.33 40-26.33 40 0v206.26h114.81v-153c0-26.33 40-26.33 40 0v153h114.82v-206.26c0-26.33 40-26.33 40 0v206.26zm-545.23-228.68c-21.19 0-27.79-29-8.54-38.09l139.79-65.96c5.4-2.56 11.65-2.56 17.07 0l118.26 55.81 66.19-54.1-19.07 4.18c-25.72 5.6-34.29-33.43-8.56-39.09l98.26-21.52c4.64-1.81 9.29-1.56 13.39.09 7.14 2.52 12.45 9.06 13.31 16.69.57 3.65.1 7.46-1.74 11.04l-26.16 79.76c-2.76 8.43-10.59 13.79-19 13.79-23.37 0-21.17-21.09-14.49-42.67l-86.59 70.77c-5.97 4.89-14.21 5.89-21.19 2.6l-121.14-57.17c-18.07 8.52-129.96 63.87-139.78 63.87z" fill="#b2e1f2"/>
      </g>
    </svg>
  ));

  ComparisonIcon.displayName = 'ComparisonIcon';

  // Custom header component for Portfolio column with icon and tooltip
  const PortfolioHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    const tooltipText = 'Нажмите на плюс, чтобы добавить облигацию в портфель. Портфель отображается во вкладке "Мой портфель"';

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
          <PortfolioIcon />
        </div>
      </Tooltip>
    );
  });

  PortfolioHeaderWithTooltip.displayName = 'PortfolioHeaderWithTooltip';

  // Custom header component for Comparison column with icon and tooltip
  const ComparisonHeaderWithTooltip = React.memo((_params: IHeaderParams) => {
    const tooltipText = 'Нажмите на плюс, чтобы добавить облигацию к сравнению. Сравнение отображается во вкладке "Сравнение облигаций"';

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
          <ComparisonIcon />
        </div>
      </Tooltip>
    );
  });

  ComparisonHeaderWithTooltip.displayName = 'ComparisonHeaderWithTooltip';

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
      field: 'addToComparison',
      headerName: '',
      minWidth: 55,
      width: 55,
      pinned: 'right',
      sortable: false,
      filter: false,
      suppressMenu: true,
      resizable: false, // Prevent column resizing to avoid layout shifts
      cellRenderer: AddToComparisonRenderer,
      cellStyle: { textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center' },
      cellClass: 'comparison-action-cell', // Add class for easier identification
      headerClass: 'ag-header-center',
      headerComponent: ComparisonHeaderWithTooltip,
      autoHeaderHeight: true,
      suppressSizeToFit: true, // Prevent auto-sizing to avoid layout shifts
    },
    {
      field: 'addToPortfolio',
      headerName: '',
      minWidth: 55,
      width: 55,
      pinned: 'right',
      sortable: false,
      filter: false,
      suppressMenu: true,
      resizable: false, // Prevent column resizing to avoid layout shifts
      cellRenderer: AddToPortfolioRenderer,
      cellStyle: { textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center' },
      cellClass: 'portfolio-action-cell', // Add class for easier identification
      headerClass: 'ag-header-center',
      headerComponent: PortfolioHeaderWithTooltip,
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

  // Track if cell click was on portfolio or comparison column to prevent row click
  const portfolioCellClickedRef = useRef(false);
  const comparisonCellClickedRef = useRef(false);

  // Handle cell click - intercept clicks on portfolio and comparison columns
  const onCellClicked = useCallback((event: CellClickedEvent) => {
    const colId = event.column?.getColId();
    // If clicking on "Add to Portfolio" or "Add to Comparison" column, mark it and prevent row click
    if (colId === 'addToPortfolio') {
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
    if (colId === 'addToComparison') {
      comparisonCellClickedRef.current = true;
      // Prevent event propagation
      if (event.event) {
        event.event.stopPropagation();
        event.event.preventDefault();
      }
      // Reset flag after a short delay to allow row click check
      setTimeout(() => {
        comparisonCellClickedRef.current = false;
      }, 200);
      return;
    }
  }, []);

  // Handle row click
  const onRowClicked = useCallback((event: RowClickedEvent) => {
    // Get the clicked element FIRST - we need it for all checks
    const target = event.event?.target as HTMLElement | null;
    if (!target || !event.event) {
      return;
    }
    
    // PRIORITY CHECK: Don't open details if portfolio or comparison cell was clicked
    // Check 1: Portfolio or comparison cell clicked flag (set by onCellClicked)
    if (portfolioCellClickedRef.current || comparisonCellClickedRef.current) {
      return;
    }
    
    // Check 2: data-portfolio-cell or data-comparison-cell attribute in click path
    if (target.closest('[data-portfolio-cell]') || target.closest('[data-comparison-cell]')) {
      return;
    }
    
    // Check 3: Find the cell element that was clicked and check its col-id
    const clickedCell = target.closest('.ag-cell');
    if (clickedCell) {
      const colId = clickedCell.getAttribute('col-id');
      if (colId === 'addToPortfolio' || colId === 'addToComparison') {
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
    // Padding: 4px top + 4px bottom = 8px, plus cell padding: 2px + 2px = 4px
    const calculatedHeight = Math.max(Math.ceil(maxContentHeight) + 12, 40);

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

  // Track previous bonds for auto-sizing on initial load
  const prevBondsRef = useRef<BondListItem[]>([]);

  // Filter bonds by search query
  const filteredBonds = useMemo(() => {
    if (!filters.search || filters.search.trim() === '') {
      return bonds;
    }
    
    const searchLower = filters.search.toLowerCase().trim();
    return bonds.filter(bond => {
      const secid = bond.SECID?.toLowerCase() || '';
      const shortname = bond.SHORTNAME?.toLowerCase() || '';
      const secname = bond.SECNAME?.toLowerCase() || '';
      const isin = bond.ISIN?.toLowerCase() || '';
      return secid.includes(searchLower) || 
             shortname.includes(searchLower) || 
             secname.includes(searchLower) || 
             isin.includes(searchLower);
    });
  }, [bonds, filters.search]);


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
        prevBondsRef.current = bonds;
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [bonds.length, columnDefs, fieldDescriptions, calculateHeaderHeight, bonds]);


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
        <Box sx={{ px: 2, width: '100%', height: '100%' }}>
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
              padding: '4px 4px',
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
              lineHeight: 1.3,
              flex: '0 1 auto',
              minWidth: 0,
              padding: '2px 0px 2px 8px !important',
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
              fontSize: '12px',
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
            // Unified font style and styling for cells
            '& .ag-cell': {
              fontFamily: 'Roboto, Helvetica, Arial, sans-serif',
              fontSize: '14px',
              lineHeight: 1.35,
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
            // Add vertical divider between comparison and portfolio columns
            '& .ag-pinned-right-cols-container .ag-cell[col-id="addToComparison"]': {
              borderRight: '1px solid #dee2e6 !important',
            },
            '& .ag-pinned-right-header .ag-header-cell': {
              background: '#fafafa !important',
              borderRight: 'none !important',
            },
            // Add vertical divider in header between comparison and portfolio columns
            '& .ag-pinned-right-header .ag-header-cell[col-id="addToComparison"]': {
              borderRight: '1px solid #dee2e6 !important',
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
            animateRows={true}
            pagination={true}
            paginationPageSize={100}
            paginationPageSizeSelector={[50, 100, 200, 500]}
            enableCellTextSelection={true}
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
        </Box>
      </CardContent>
    </Card>
  );
};

BondsTable.displayName = 'BondsTable';

export default BondsTable;
