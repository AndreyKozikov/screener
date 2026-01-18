import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import {
  Box,
  Card,
  CardContent,
  Button,
  Stack,
  Typography,
  Paper,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { type Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import DescriptionIcon from '@mui/icons-material/Description';
import { fetchKeyRateData, downloadKeyRateMarkdown, type KeyRateRecord } from '../../api/keyrate';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import { EmptyState } from '../common/EmptyState';
import { formatNumber } from '../../utils/formatters';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

// Configure dayjs
dayjs.extend(customParseFormat);
dayjs.locale('ru');

/**
 * KeyRateTable Component
 *
 * Displays key rate data in a table with date filters
 */
export const KeyRateTable: React.FC = () => {
  const [data, setData] = useState<KeyRateRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
  const [dateTo, setDateTo] = useState<Dayjs | null>(null);

  // Helper function to format dayjs date to DD.MM.YYYY string
  const formatDateToString = (date: Dayjs | null): string | null => {
    if (!date) return null;
    return date.format('DD.MM.YYYY');
  };

  // Helper function to format date from YYYY-MM-DD to DD.MM.YYYY
  const formatDateForDisplay = (dateStr: string): string => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [year, month, day] = dateStr.split('-');
      return `${day}.${month}.${year}`;
    }
    return dateStr;
  };

  // Set default date range (60 days ago to today) and load data
  useEffect(() => {
    const today = dayjs();
    const sixtyDaysAgo = today.subtract(60, 'day');

    setDateFrom(sixtyDaysAgo);
    setDateTo(today);

    // Load data with default dates
    const loadDefaultData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const fromStr = formatDateToString(sixtyDaysAgo);
        const toStr = formatDateToString(today);
        if (!fromStr || !toStr) return;
        
        const response = await fetchKeyRateData(fromStr, toStr);
        console.log('Key rate data loaded:', response.count, 'records');
        setData(response.data);
      } catch (err) {
        console.error('Error loading key rate data:', err);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Не удалось загрузить данные ключевой ставки');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void loadDefaultData();
  }, []);

  const loadData = useCallback(async () => {
    if (!dateFrom || !dateTo) return;

    try {
      setIsLoading(true);
      setError(null);
      const fromStr = formatDateToString(dateFrom);
      const toStr = formatDateToString(dateTo);
      if (!fromStr || !toStr) return;
      
      const response = await fetchKeyRateData(fromStr, toStr);
      console.log('Key rate data loaded:', response.count, 'records');
      setData(response.data);
    } catch (err) {
      console.error('Error loading key rate data:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось загрузить данные ключевой ставки');
      }
    } finally {
      setIsLoading(false);
    }
  }, [dateFrom, dateTo]);

  const handleDownloadMarkdown = useCallback(async () => {
    if (!dateFrom || !dateTo) return;
    
    try {
      const fromStr = formatDateToString(dateFrom);
      const toStr = formatDateToString(dateTo);
      if (!fromStr || !toStr) return;
      
      await downloadKeyRateMarkdown(fromStr, toStr);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось скачать файл');
      }
    }
  }, [dateFrom, dateTo]);

  // Column definitions
  const columnDefs = useMemo<ColDef[]>(() => {
    return [
      {
        field: 'Дата',
        headerName: 'Дата',
        flex: 1,
        sortable: true,
        filter: true,
        wrapHeaderText: true,
        autoHeaderHeight: true,
        valueFormatter: (params) => {
          if (!params.value) return '';
          return formatDateForDisplay(params.value);
        },
        cellStyle: { textAlign: 'center' },
        headerClass: 'text-center',
      },
      {
        field: 'Ключевая ставка, % годовых',
        headerName: 'Ключевая ставка, % годовых',
        flex: 1,
        sortable: true,
        filter: true,
        wrapHeaderText: true,
        autoHeaderHeight: true,
        valueFormatter: (params) => {
          if (params.value === null || params.value === undefined) {
            return '';
          }
          return formatNumber(params.value, 2);
        },
        valueGetter: (params) => {
          if (params.data && params.data['Ключевая ставка, % годовых'] !== null && params.data['Ключевая ставка, % годовых'] !== undefined) {
            return typeof params.data['Ключевая ставка, % годовых'] === 'number' ? params.data['Ключевая ставка, % годовых'] : null;
          }
          return null;
        },
        cellStyle: { textAlign: 'center' },
        type: 'numericColumn',
        headerClass: 'text-center',
      },
    ];
  }, []);

  const defaultColDef = useMemo<ColDef>(
    () => ({
      resizable: true,
      sortable: true,
      filter: true,
    }),
    []
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
      {/* Filters Panel */}
      <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="ru">
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Фильтры по дате:
            </Typography>
            <DatePicker
              label="Дата от"
              value={dateFrom}
              onChange={(newValue) => setDateFrom(newValue)}
              format="DD.MM.YYYY"
              slotProps={{
                textField: {
                  size: 'small',
                  sx: { width: 180 },
                },
              }}
            />
            <DatePicker
              label="Дата до"
              value={dateTo}
              onChange={(newValue) => setDateTo(newValue)}
              format="DD.MM.YYYY"
              slotProps={{
                textField: {
                  size: 'small',
                  sx: { width: 180 },
                },
              }}
            />
            <Button
              variant="contained"
              onClick={loadData}
              disabled={isLoading || !dateFrom || !dateTo}
            >
              Применить
            </Button>
            <Button
              variant="outlined"
              startIcon={<DescriptionIcon />}
              onClick={handleDownloadMarkdown}
              disabled={isLoading || data.length === 0}
            >
              Скачать в Markdown
            </Button>
            {data.length > 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
                Записей: {data.length}
              </Typography>
            )}
          </Stack>
        </Paper>
      </LocalizationProvider>

      {/* Table */}
      <Card sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 0, '&:last-child': { pb: 0 } }}>
          {error && <ErrorMessage message={error} />}
          {isLoading && <LoadingSpinner />}
          {!isLoading && !error && data.length === 0 && (
            <EmptyState message="Нет данных за выбранный период" />
          )}
          {!isLoading && !error && data.length > 0 && (
            <Box 
              sx={{ 
                width: '100%', 
                height: '100%', 
                minHeight: 400,
                '& .ag-header-cell-label': {
                  justifyContent: 'center',
                },
                '& .text-center': {
                  textAlign: 'center',
                  '& .ag-header-cell-text': {
                    textAlign: 'center',
                    width: '100%',
                  },
                },
                '& .ag-theme-material': {
                  '--ag-cell-horizontal-border': 'solid 1px rgba(224, 224, 224, 1)',
                  '--ag-header-column-separator-display': 'block',
                  '--ag-header-column-separator-height': '100%',
                  '--ag-header-column-separator-width': '1px',
                  '--ag-header-column-separator-color': 'rgba(224, 224, 224, 1)',
                },
              }}
            >
              <AgGridReact
                rowData={data}
                columnDefs={columnDefs}
                defaultColDef={defaultColDef}
                animateRows={true}
                rowSelection="multiple"
                suppressRowClickSelection={true}
                pagination={true}
                paginationPageSize={50}
                paginationPageSizeSelector={[25, 50, 100, 200]}
                domLayout="normal"
                className="ag-theme-material"
                theme="legacy"
              />
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};
