import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import '../bonds/registerGridModules';
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
import AssessmentIcon from '@mui/icons-material/Assessment';
import type { SxProps, Theme } from '@mui/material/styles';
import { fetchForecastData, fetchForecastDates, downloadForecastJson, type ForecastData } from '../../api/forecast';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import { EmptyState } from '../common/EmptyState';
import { formatNumber } from '../../utils/formatters';

/** Акцентный цвет раздела «Прогнозы» (совпадает с карточкой на главной) */
const ACCENT_COLOR = '#ff9800';

/** Стеклянная панель в стиле главной страницы */
const glassPanelSx: SxProps<Theme> = {
  position: 'relative',
  borderRadius: { xs: '16px', md: '22px' },
  border: '1px solid rgba(255,255,255,0.82)',
  background: 'linear-gradient(145deg, rgba(255,255,255,0.62), rgba(255,255,255,0.46))',
  backdropFilter: 'blur(22px) saturate(145%)',
  boxShadow: '0 14px 34px rgba(68, 104, 171, 0.12), inset 0 1px 0 rgba(255,255,255,0.8)',
  overflow: 'hidden',
};

const tableTitleSx: SxProps<Theme> = {
  mb: { xs: 1.25, md: 1.75 },
  fontSize: { xs: '0.98rem', md: '1.12rem' },
  lineHeight: 1.3,
  fontWeight: 650,
  letterSpacing: '0.005em',
  color: '#10264A',
};

const glassControlSx: SxProps<Theme> = {
  '& .MuiInputLabel-root': { color: '#3E5577', fontWeight: 500 },
  '& .MuiInputLabel-root.Mui-focused': { color: '#1769E8' },
  '& .MuiOutlinedInput-root': {
    borderRadius: '999px',
    color: '#10264A',
    fontWeight: 600,
    bgcolor: 'rgba(255,255,255,0.5)',
    backdropFilter: 'blur(14px)',
    transition: 'background-color 180ms ease, box-shadow 180ms ease',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.9)' },
    '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
    '&:hover fieldset': { borderColor: 'rgba(23, 105, 232, 0.35)' },
    '&.Mui-focused fieldset': { borderColor: '#1769E8', borderWidth: 1.5 },
    '&.Mui-focused': { boxShadow: '0 0 0 4px rgba(23, 105, 232, 0.12)' },
  },
  '& .MuiSelect-icon': { color: '#29476F' },
};

const glassMenuSx: SxProps<Theme> = {
  mt: 0.75,
  borderRadius: '16px',
  border: '1px solid rgba(255,255,255,0.86)',
  background: 'rgba(255,255,255,0.86)',
  backdropFilter: 'blur(22px) saturate(145%)',
  boxShadow: '0 14px 34px rgba(68, 104, 171, 0.18)',
  '& .MuiMenuItem-root': { color: '#10264A', fontWeight: 500, mx: 0.75, borderRadius: '10px' },
  '& .MuiMenuItem-root.Mui-selected': { bgcolor: 'rgba(23, 105, 232, 0.12)' },
  '& .MuiMenuItem-root:hover': { bgcolor: 'rgba(23, 105, 232, 0.08)' },
};

const glassButtonSx: SxProps<Theme> = {
  borderRadius: '999px',
  px: 2.25,
  textTransform: 'none',
  fontWeight: 650,
  color: '#1769E8',
  borderColor: 'rgba(255,255,255,0.9)',
  bgcolor: 'rgba(255,255,255,0.5)',
  backdropFilter: 'blur(14px)',
  boxShadow: '0 3px 10px rgba(63, 104, 174, 0.1)',
  transition: 'background-color 180ms ease, box-shadow 180ms ease, transform 180ms ease',
  '&:hover': {
    bgcolor: 'rgba(255,255,255,0.78)',
    borderColor: 'rgba(23, 105, 232, 0.35)',
    boxShadow: '0 8px 18px rgba(63, 104, 174, 0.16)',
    transform: 'translateY(-1px)',
  },
  '&.Mui-disabled': { color: '#8FA3C2', borderColor: 'rgba(255,255,255,0.7)', bgcolor: 'rgba(255,255,255,0.3)' },
};

const INDICATOR_CELL_STYLE = { fontWeight: 500, borderRight: '1px solid rgba(120, 150, 200, 0.28)' };

export interface ForecastTableProps {
  /** Если передан (массив из комнаты «Прогнозы»), запрос /forecast/dates не выполняется */
  initialDates?: string[] | null;
}

/**
 * ForecastTable Component
 *
 * Displays Bank of Russia forecast data in tables with date selection
 */
export const ForecastTable: React.FC<ForecastTableProps> = ({ initialDates }) => {
  const [data, setData] = useState<ForecastData | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Использовать переданные даты или загрузить при монтировании (без дублирования запроса из комнаты Прогнозы)
  useEffect(() => {
    if (initialDates != null) {
      const list = Array.isArray(initialDates) ? initialDates : [];
      setAvailableDates(list);
      setSelectedDate(list.length > 0 ? list[0] : '');
      setError(null);
      return;
    }
    const loadDates = async () => {
      try {
        const dates = await fetchForecastDates();
        const list = Array.isArray(dates) ? dates : [];
        setAvailableDates(list);
        if (list.length > 0) {
          setSelectedDate(list[0]);
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
  }, [initialDates]);

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
        cellStyle: INDICATOR_CELL_STYLE,
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
        cellStyle: INDICATOR_CELL_STYLE,
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
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: { xs: 1.5, md: 2 }, color: '#10264A' }}>
      {/* Header with date selection and export */}
      <Paper elevation={0} sx={{ ...glassPanelSx, px: { xs: 2, md: 3 }, py: { xs: 1.5, md: 2 } }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
          <Box
            aria-hidden="true"
            sx={{
              flexShrink: 0,
              width: { xs: 42, md: 50 },
              height: { xs: 42, md: 50 },
              display: 'grid',
              placeItems: 'center',
              borderRadius: '14px',
              color: '#FFFFFF',
              background: `linear-gradient(145deg, ${ACCENT_COLOR}, ${ACCENT_COLOR}D9)`,
              boxShadow: `0 6px 14px ${ACCENT_COLOR}32`,
              '& svg': { fontSize: { xs: 24, md: 28 } },
            }}
          >
            <AssessmentIcon />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography
              component="h2"
              sx={{ fontSize: { xs: '1.15rem', md: '1.45rem' }, lineHeight: 1.2, fontWeight: 700, letterSpacing: '0.005em', color: '#10264A' }}
            >
              Среднесрочный прогноз Банка России
            </Typography>
            {data && (
              <Typography sx={{ mt: 0.35, fontSize: { xs: '0.82rem', md: '0.92rem' }, lineHeight: 1.4, color: '#587092' }}>
                Дата заседания: {formatDateDisplay(data.data.дата_заседания)}
              </Typography>
            )}
          </Box>
          <FormControl size="small" sx={{ minWidth: 230, ml: { xs: 0, sm: 'auto' }, ...glassControlSx }}>
            <InputLabel id="forecast-date-select-label">Выберите дату</InputLabel>
            <Select
              labelId="forecast-date-select-label"
              key={availableDates.length > 0 ? availableDates[0] : 'empty'}
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              label="Выберите дату"
              MenuProps={{ PaperProps: { sx: glassMenuSx } }}
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
            sx={glassButtonSx}
          >
            Экспорт в JSON
          </Button>
        </Stack>
      </Paper>

      {/* Tables */}
      {error && <ErrorMessage message={error} />}
      {isLoading && <LoadingSpinner />}
      {!isLoading && !error && data && (
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', lg: 'row' }, gap: { xs: 1.5, md: 2.5 }, flexGrow: 1, minHeight: 0 }}>
          {/* Main Indicators Table */}
          <Card elevation={0} sx={{ ...glassPanelSx, flex: 1, display: 'flex', flexDirection: 'column', minHeight: { xs: 360, lg: 0 } }}>
            <CardContent sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, p: { xs: 1.5, md: 2.25 }, '&:last-child': { pb: { xs: 1.5, md: 2.25 } } }}>
              <Typography component="h3" sx={tableTitleSx}>
                Основные параметры прогноза
              </Typography>
              <Box sx={{ width: '100%', flex: 1, minHeight: 0, height: '100%' }}>
                <AgGridReact
                  rowData={mainIndicatorsRows}
                  columnDefs={mainIndicatorsColumns}
                  defaultColDef={defaultColDef}
                  headerHeight={64}
                  animateRows={true}
                  domLayout="normal"
                  className="ag-theme-material forecast-table"
                  theme="legacy"
                />
              </Box>
            </CardContent>
          </Card>

          {/* Balance Table */}
          <Card elevation={0} sx={{ ...glassPanelSx, flex: 1, display: 'flex', flexDirection: 'column', minHeight: { xs: 360, lg: 0 } }}>
            <CardContent sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, p: { xs: 1.5, md: 2.25 }, '&:last-child': { pb: { xs: 1.5, md: 2.25 } } }}>
              <Typography component="h3" sx={tableTitleSx}>
                Показатели платёжного баланса
              </Typography>
              <Box sx={{ width: '100%', flex: 1, minHeight: 0, height: '100%' }}>
                <AgGridReact
                  rowData={balanceRows}
                  columnDefs={balanceColumns}
                  defaultColDef={defaultColDef}
                  headerHeight={64}
                  animateRows={true}
                  domLayout="normal"
                  className="ag-theme-material forecast-table"
                  theme="legacy"
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




