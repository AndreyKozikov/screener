import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-material.css';
import './forecast-table.css';
import {
  Box,
  Card,
  CardContent,
  Button,
  Stack,
  Typography,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { fetchForecastData, fetchForecastDates, downloadForecastJson, type ForecastData } from '../../api/forecast';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import { EmptyState } from '../common/EmptyState';
import { formatNumber } from '../../utils/formatters';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

/**
 * ForecastTable Component
 *
 * Displays Bank of Russia forecast data in tables with date selection
 */
export const ForecastTable: React.FC = () => {
  const [data, setData] = useState<ForecastData | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available dates on mount
  useEffect(() => {
    const loadDates = async () => {
      try {
        const dates = await fetchForecastDates();
        setAvailableDates(dates);
        if (dates.length > 0) {
          setSelectedDate(dates[0]); // Set latest date as default
        }
      } catch (err) {
        console.error('Error loading forecast dates:', err);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Не удалось загрузить список дат');
        }
      }
    };

    void loadDates();
  }, []);

  // Load data when date changes
  useEffect(() => {
    if (!selectedDate) return;

    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const forecastData = await fetchForecastData(selectedDate);
        setData(forecastData);
      } catch (err) {
        console.error('Error loading forecast data:', err);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Не удалось загрузить данные прогноза');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void loadData();
  }, [selectedDate]);

  const handleDownload = useCallback(async () => {
    if (!selectedDate) return;

    try {
      await downloadForecastJson([selectedDate]);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось скачать файл');
      }
    }
  }, [selectedDate]);

  // Format date for display
  const formatDateDisplay = (dateStr: string): string => {
    const date = new Date(dateStr);
    const months = [
      'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ];
    return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()} года`;
  };

  // Generate column definitions for main indicators table
  const mainIndicatorsColumns = useMemo<ColDef[]>(() => {
    if (!data || !data.data.основные_показатели.length) return [];

    const indicators = data.data.основные_показатели;
    const years = [...new Set(indicators.map(ind => ind.год))].sort();

    const cols: ColDef[] = [
      {
        field: 'indicator',
        headerName: 'Показатель',
        width: 400,
        pinned: 'left',
        sortable: false,
        filter: false,
        wrapText: true,
        autoHeight: true,
        cellStyle: { fontWeight: 500, borderRight: '2px solid #e0e0e0' },
        cellClass: 'forecast-indicator-cell',
        headerClass: 'ag-header-cell-center forecast-header forecast-indicator-header',
      },
    ];

    years.forEach(year => {
      cols.push({
        field: `year_${year}`,
        headerName: String(year),
        width: 150,
        sortable: false,
        filter: false,
        cellStyle: { textAlign: 'center' },
        cellClass: 'forecast-year-cell',
        headerClass: 'ag-header-cell-center forecast-header',
      });
    });

    return cols;
  }, [data]);

  // Generate row data for main indicators table
  const mainIndicatorsRows = useMemo(() => {
    if (!data || !data.data.основные_показатели.length) return [];

    const names = data.names.основные_показатели;
    const indicators = data.data.основные_показатели;
    const years = [...new Set(indicators.map(ind => ind.год))].sort();

    const rows: Record<string, any>[] = [];

    // Get all indicator keys (excluding 'год')
    const indicatorKeys = new Set<string>();
    indicators.forEach(ind => {
      Object.keys(ind).forEach(key => {
        if (key !== 'год') {
          indicatorKeys.add(key);
        }
      });
    });

    indicatorKeys.forEach(key => {
      if (!names[key]) return;

      const row: Record<string, any> = {
        indicator: names[key],
      };

      years.forEach(year => {
        const yearData = indicators.find(ind => ind.год === year);
        if (yearData && key in yearData) {
          const value = yearData[key];
          if (value && typeof value === 'object' && 'мин' in value && 'макс' in value) {
            const val = value as { мин: number; макс: number };
            if (val.мин === val.макс) {
              row[`year_${year}`] = formatNumber(val.мин, 1);
            } else {
              row[`year_${year}`] = `${formatNumber(val.мин, 1)}–${formatNumber(val.макс, 1)}`;
            }
          } else if (value !== null && value !== undefined) {
            row[`year_${year}`] = String(value);
          } else {
            row[`year_${year}`] = '-';
          }
        } else {
          row[`year_${year}`] = '-';
        }
      });

      rows.push(row);
    });

    return rows;
  }, [data]);

  // Generate column definitions for balance table
  const balanceColumns = useMemo<ColDef[]>(() => {
    if (!data || !data.data.платёжный_баланс.length) return [];

    const indicators = data.data.платёжный_баланс;
    const years = [...new Set(indicators.map(ind => ind.год))].sort();

    const cols: ColDef[] = [
      {
        field: 'indicator',
        headerName: 'Показатель',
        width: 500,
        pinned: 'left',
        sortable: false,
        filter: false,
        wrapText: true,
        autoHeight: true,
        cellStyle: { fontWeight: 500, borderRight: '2px solid #e0e0e0' },
        cellClass: 'forecast-indicator-cell',
        headerClass: 'ag-header-cell-center forecast-header forecast-indicator-header',
      },
    ];

    years.forEach(year => {
      cols.push({
        field: `year_${year}`,
        headerName: String(year),
        width: 150,
        sortable: false,
        filter: false,
        cellStyle: { textAlign: 'center' },
        cellClass: 'forecast-year-cell',
        headerClass: 'ag-header-cell-center forecast-header',
      });
    });

    return cols;
  }, [data]);

  // Generate row data for balance table
  const balanceRows = useMemo(() => {
    if (!data || !data.data.платёжный_баланс.length) return [];

    const names = data.names.платёжный_баланс;
    const indicators = data.data.платёжный_баланс;
    const years = [...new Set(indicators.map(ind => ind.год))].sort();

    const rows: Record<string, any>[] = [];

    const indicatorKeys = new Set<string>();
    indicators.forEach(ind => {
      Object.keys(ind).forEach(key => {
        if (key !== 'год') {
          indicatorKeys.add(key);
        }
      });
    });

    indicatorKeys.forEach(key => {
      if (!names[key]) return;

      const row: Record<string, any> = {
        indicator: names[key],
      };

      years.forEach(year => {
        const yearData = indicators.find(ind => ind.год === year);
        if (yearData && key in yearData) {
          const value = yearData[key];
          if (value !== null && value !== undefined) {
            row[`year_${year}`] = formatNumber(value as number, 1);
          } else {
            row[`year_${year}`] = '-';
          }
        } else {
          row[`year_${year}`] = '-';
        }
      });

      rows.push(row);
    });

    return rows;
  }, [data]);

  const defaultColDef = useMemo<ColDef>(
    () => ({
      resizable: true,
      sortable: false,
      filter: false,
    }),
    []
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
      {/* Header with date selection and export */}
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Среднесрочный прогноз Банка России
          </Typography>
          {data && (
            <Typography variant="body1" color="text.secondary">
              Дата заседания: {formatDateDisplay(data.data.дата_заседания)}
            </Typography>
          )}
          <FormControl size="small" sx={{ minWidth: 200, ml: 'auto' }}>
            <InputLabel>Выберите дату</InputLabel>
            <Select
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              label="Выберите дату"
            >
              {availableDates.map(date => (
                <MenuItem key={date} value={date}>
                  {formatDateDisplay(date)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownload}
            disabled={isLoading || !data}
          >
            Экспорт в JSON
          </Button>
        </Stack>
      </Paper>

      {/* Tables */}
      {error && <ErrorMessage message={error} />}
      {isLoading && <LoadingSpinner />}
      {!isLoading && !error && data && (
        <Box sx={{ display: 'flex', flexDirection: 'row', gap: 3, flexGrow: 1, minHeight: 0 }}>
          {/* Main Indicators Table */}
          <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <CardContent sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, '&:last-child': { pb: 2 } }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
                Основные параметры прогноза
              </Typography>
              <Box sx={{ width: '100%', flex: 1, minHeight: 0 }}>
                <AgGridReact
                  rowData={mainIndicatorsRows}
                  columnDefs={mainIndicatorsColumns}
                  defaultColDef={defaultColDef}
                  headerHeight={64}
                  animateRows={true}
                  domLayout="normal"
                  style={{ width: '100%', height: '100%' }}
                  className="ag-theme-material forecast-table"
                />
              </Box>
            </CardContent>
          </Card>

          {/* Balance Table */}
          <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <CardContent sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, '&:last-child': { pb: 2 } }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
                Показатели платёжного баланса
              </Typography>
              <Box sx={{ width: '100%', flex: 1, minHeight: 0 }}>
                <AgGridReact
                  rowData={balanceRows}
                  columnDefs={balanceColumns}
                  defaultColDef={defaultColDef}
                  headerHeight={64}
                  animateRows={true}
                  domLayout="normal"
                  style={{ width: '100%', height: '100%' }}
                  className="ag-theme-material forecast-table"
                />
              </Box>
            </CardContent>
          </Card>
        </Box>
      )}
      {!isLoading && !error && !data && (
        <EmptyState message="Нет данных для отображения" />
      )}
    </Box>
  );
};

