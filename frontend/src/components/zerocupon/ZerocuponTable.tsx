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
import DownloadIcon from '@mui/icons-material/Download';
import { fetchZerocuponData, downloadZerocuponJson, type ZerocuponRecord } from '../../api/zerocupon';
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
 * ZerocuponTable Component
 *
 * Displays zero-coupon yield curve data in a table with date filters
 */
export const ZerocuponTable: React.FC = () => {
  const [data, setData] = useState<ZerocuponRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
  const [dateTo, setDateTo] = useState<Dayjs | null>(null);

  // Helper function to format dayjs date to DD.MM.YYYY string
  const formatDateToString = (date: Dayjs | null): string | null => {
    if (!date) return null;
    return date.format('DD.MM.YYYY');
  };

  // Set default date range to last year and load data
  useEffect(() => {
    const today = dayjs();
    const oneYearAgo = today.subtract(1, 'year');

    setDateFrom(oneYearAgo);
    setDateTo(today);

    // Load data with default dates
    const loadDefaultData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const fromStr = formatDateToString(oneYearAgo);
        const toStr = formatDateToString(today);
        if (!fromStr || !toStr) return;
        
        const response = await fetchZerocuponData(fromStr, toStr);
        console.log('Zerocupon data loaded:', response.count, 'records');
        console.log('First record:', response.data[0]);
        setData(response.data);
      } catch (err) {
        console.error('Error loading zerocupon data:', err);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Не удалось загрузить данные БКДЦТ');
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
      
      const response = await fetchZerocuponData(fromStr, toStr);
      console.log('Zerocupon data loaded:', response.count, 'records');
      if (response.data.length > 0) {
        console.log('First record:', response.data[0]);
        console.log('Record keys:', Object.keys(response.data[0]));
      }
      setData(response.data);
    } catch (err) {
      console.error('Error loading zerocupon data:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось загрузить данные БКДЦТ');
      }
    } finally {
      setIsLoading(false);
    }
  }, [dateFrom, dateTo]);

  const handleDownload = useCallback(async () => {
    if (!dateFrom || !dateTo) return;
    
    try {
      const fromStr = formatDateToString(dateFrom);
      const toStr = formatDateToString(dateTo);
      if (!fromStr || !toStr) return;
      
      await downloadZerocuponJson(fromStr, toStr);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось скачать файл');
      }
    }
  }, [dateFrom, dateTo]);

  // Generate column definitions dynamically based on data
  const columnDefs = useMemo<ColDef[]>(() => {
    if (data.length === 0) return [];

    const firstRecord = data[0];
    const cols: ColDef[] = [];

    // Fixed columns: Дата, Время
    cols.push({
      field: 'Дата',
      headerName: 'Дата',
      width: 120,
      pinned: 'left',
      sortable: true,
      filter: true,
    });

    cols.push({
      field: 'Время',
      headerName: 'Время',
      width: 100,
      pinned: 'left',
      sortable: true,
      filter: true,
    });

    // Dynamic period columns (sorted by numeric value)
    const periodFields = Object.keys(firstRecord)
      .filter((key) => key !== 'Дата' && key !== 'Время')
      .sort((a, b) => {
        // Extract numeric value from "Срок X.Y лет"
        const extractValue = (str: string): number => {
          const match = str.match(/Срок\s+(\d+(?:\.\d+)?)\s+лет/);
          return match ? parseFloat(match[1]) : 0;
        };
        return extractValue(a) - extractValue(b);
      });

    periodFields.forEach((field) => {
      cols.push({
        field,
        headerName: field,
        width: 130,
        sortable: true,
        filter: true,
        valueFormatter: (params) => {
          if (params.value === null || params.value === undefined || params.value === '') {
            return '';
          }
          // Handle both string and number types
          let num: number;
          if (typeof params.value === 'string') {
            // Remove any spaces and replace comma with dot
            const cleaned = params.value.trim().replace(',', '.');
            num = parseFloat(cleaned);
          } else {
            num = params.value;
          }
          if (isNaN(num)) return '';
          return formatNumber(num, 4);
        },
        valueGetter: (params) => {
          // Ensure numeric value for sorting/filtering
          if (params.data && params.data[field] !== null && params.data[field] !== undefined) {
            const val = params.data[field];
            if (typeof val === 'string') {
              const cleaned = val.trim().replace(',', '.');
              const num = parseFloat(cleaned);
              return isNaN(num) ? null : num;
            }
            return typeof val === 'number' ? val : null;
          }
          return null;
        },
        cellStyle: { textAlign: 'right' },
        type: 'numericColumn',
      });
    });

    return cols;
  }, [data]);

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
              startIcon={<DownloadIcon />}
              onClick={handleDownload}
              disabled={isLoading || data.length === 0}
            >
              Скачать JSON
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
            <Box sx={{ width: '100%', height: '100%', minHeight: 400 }}>
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
                style={{ width: '100%', height: '100%' }}
                className="ag-theme-material"
              />
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

