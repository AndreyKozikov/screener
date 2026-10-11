import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Stack,
  CircularProgress,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Divider,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { type Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import Plot from 'react-plotly.js';
import {
  fetchInflationExpectationsData,
  type InflationExpectationsDataPoint,
} from '../../api/inflationExpectationsApi';

interface ProcessedPoint {
  recorddata: string;
  formattedDate: string;
  observed: number | null;
  observedDiff: number | null;
  expected1y: number | null;
  expected1yDiff: number | null;
  expected5y: number | null;
  expected5yDiff: number | null;
  gap: number | null;
  gapDiff: number | null;
}

const formatDiff = (diff: number | null, unit: string = 'п.п.'): string => {
  if (diff === null || isNaN(diff)) return '';
  const sign = diff > 0 ? '+' : '';
  return ` (${sign}${diff.toFixed(2)} ${unit})`;
};

const formatDiffBadge = (diff: number | null, unit: string = 'п.п.'): string => {
  if (diff === null || isNaN(diff)) return '— к пред. мес.';
  const sign = diff > 0 ? '+' : '';
  return `${sign}${diff.toFixed(2)} ${unit} к пред. мес.`;
};

const formatValue = (val: number | null, suffix: string = '%'): string => {
  if (val === null || isNaN(val)) return '—';
  return `${val.toFixed(2)}${suffix}`;
};

const getDiffColor = (diff: number | null): string => {
  if (diff === null || isNaN(diff) || diff === 0) return 'text.secondary';
  return diff > 0 ? 'error.main' : 'success.main';
};

export const InflationExpectationsChart: React.FC = () => {
  const [data, setData] = useState<InflationExpectationsDataPoint[]>([]);
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
  const [dateTo, setDateTo] = useState<Dayjs | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadInflationData = useCallback(async (from?: Dayjs | null, till?: Dayjs | null) => {
    try {
      setLoading(true);
      setError(null);
      const params: { from?: string; till?: string } = {};
      if (from && from.isValid()) {
        params.from = from.format('YYYY-MM-DD');
      }
      if (till && till.isValid()) {
        params.till = till.format('YYYY-MM-DD');
      }
      const result = await fetchInflationExpectationsData(params);
      setData(result);
    } catch (err) {
      setError('Ошибка при загрузке данных по инфляционным ожиданиям');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInflationData(null, null);
  }, [loadInflationData]);

  const handleApply = () => {
    void loadInflationData(dateFrom, dateTo);
  };

  const handleReset = () => {
    setDateFrom(null);
    setDateTo(null);
    void loadInflationData(null, null);
  };

  const processedData = useMemo<ProcessedPoint[]>(() => {
    const sorted = [...data].sort((a, b) => a.recorddata.localeCompare(b.recorddata));

    return sorted.map((item, idx) => {
      const prev = idx > 0 ? sorted[idx - 1] : null;

      const observed = item.observed_annual_inflation;
      const prevObserved = prev?.observed_annual_inflation ?? null;
      const observedDiff =
        observed !== null && prevObserved !== null ? observed - prevObserved : null;

      const expected1y = item.expected_annual_inflation;
      const prevExpected1y = prev?.expected_annual_inflation ?? null;
      const expected1yDiff =
        expected1y !== null && prevExpected1y !== null ? expected1y - prevExpected1y : null;

      const expected5y = item.expected_five_year_inflation;
      const prevExpected5y = prev?.expected_five_year_inflation ?? null;
      const expected5yDiff =
        expected5y !== null && prevExpected5y !== null ? expected5y - prevExpected5y : null;

      const gap =
        expected1y !== null && observed !== null ? expected1y - observed : null;
      const prevGap =
        prev && prev.expected_annual_inflation !== null && prev.observed_annual_inflation !== null
          ? prev.expected_annual_inflation - prev.observed_annual_inflation
          : null;
      const gapDiff = gap !== null && prevGap !== null ? gap - prevGap : null;

      const d = new Date(item.recorddata);
      const formattedDate = !isNaN(d.getTime())
        ? d.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })
        : item.recorddata;

      return {
        recorddata: item.recorddata,
        formattedDate,
        observed,
        observedDiff,
        expected1y,
        expected1yDiff,
        expected5y,
        expected5yDiff,
        gap,
        gapDiff,
      };
    });
  }, [data]);

  const latest = useMemo(
    () => (processedData.length > 0 ? processedData[processedData.length - 1] : null),
    [processedData]
  );

  const recentPoints = useMemo(
    () => processedData.slice(-6).reverse(),
    [processedData]
  );

  const upperChartData = useMemo(() => {
    return [
      {
        x: processedData.map((item) => item.recorddata),
        y: processedData.map((item) => item.observed),
        customdata: processedData.map((item) => formatDiff(item.observedDiff, 'п.п.')),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Наблюдаемая инфляция',
        line: { shape: 'linear' as const, color: '#1976d2', width: 2.5 },
        marker: { size: 6, symbol: 'circle' },
        hoverlabel: { namelength: -1 },
        hovertemplate: '%{fullData.name}: <b>%{y:.2f}%</b>%{customdata}<extra></extra>',
      },
      {
        x: processedData.map((item) => item.recorddata),
        y: processedData.map((item) => item.expected1y),
        customdata: processedData.map((item) => formatDiff(item.expected1yDiff, 'п.п.')),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Ожидаемая инфляция, 1 год',
        line: { shape: 'linear' as const, color: '#d32f2f', width: 2.5 },
        marker: { size: 6, symbol: 'square' },
        hoverlabel: { namelength: -1 },
        hovertemplate: '%{fullData.name}: <b>%{y:.2f}%</b>%{customdata}<extra></extra>',
      },
      {
        x: processedData.map((item) => item.recorddata),
        y: processedData.map((item) => item.expected5y),
        customdata: processedData.map((item) => formatDiff(item.expected5yDiff, 'п.п.')),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Ожидаемая инфляция, 5 лет',
        line: { shape: 'linear' as const, color: '#2e7d32', width: 2.5, dash: 'solid' },
        marker: { size: 6, symbol: 'diamond' },
        hoverlabel: { namelength: -1 },
        hovertemplate: '%{fullData.name}: <b>%{y:.2f}%</b>%{customdata}<extra></extra>',
      },
    ];
  }, [processedData]);

  const lowerChartData = useMemo(() => {
    return [
      {
        x: processedData.map((item) => item.recorddata),
        y: processedData.map((item) => item.gap),
        customdata: processedData.map((item) => formatDiff(item.gapDiff, 'п.п.')),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Разрыв (ожидания − наблюдаемая)',
        line: { shape: 'linear' as const, color: '#ed6c02', width: 2 },
        marker: { size: 5 },
        hoverlabel: { namelength: -1 },
        hovertemplate: '%{fullData.name}: <b>%{y:.2f} п.п.</b>%{customdata}<extra></extra>',
      },
    ];
  }, [processedData]);

  return (
    <Box sx={{ width: '100%', p: 2 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="ru">
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 2,
                flexWrap: 'wrap',
                gap: 2,
              }}
            >
              <Typography variant="h6">Инфляционные ожидания населения</Typography>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <DatePicker
                  label="Дата начала"
                  value={dateFrom}
                  onChange={(newValue) => setDateFrom(newValue)}
                  maxDate={dateTo ?? undefined}
                  format="DD.MM.YYYY"
                  slotProps={{
                    textField: {
                      size: 'small',
                      sx: { width: 170 },
                    },
                  }}
                />
                <DatePicker
                  label="Дата окончания"
                  value={dateTo}
                  onChange={(newValue) => setDateTo(newValue)}
                  minDate={dateFrom ?? undefined}
                  format="DD.MM.YYYY"
                  slotProps={{
                    textField: {
                      size: 'small',
                      sx: { width: 170 },
                    },
                  }}
                />
                <Button
                  variant="contained"
                  onClick={handleApply}
                  disabled={loading}
                >
                  Применить
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleReset}
                  disabled={loading || (!dateFrom && !dateTo)}
                >
                  Сбросить
                </Button>
              </Stack>
            </Box>
          </LocalizationProvider>

          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {!loading && !error && processedData.length === 0 && (
            <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
              Нет данных за выбранный период
            </Typography>
          )}

          {!loading && !error && processedData.length > 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* KPI Summary: Latest Month */}
              {latest && (
                <Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>
                    Текущие значения ({latest.formattedDate}) и изменения к предыдущему месяцу:
                  </Typography>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: {
                        xs: '1fr',
                        sm: 'repeat(2, 1fr)',
                        md: 'repeat(4, 1fr)',
                      },
                      gap: 2,
                    }}
                  >
                    <Paper variant="outlined" sx={{ p: 2, borderLeft: '4px solid #1976d2' }}>
                      <Typography variant="caption" color="text.secondary">
                        Наблюдаемая инфляция
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {formatValue(latest.observed, '%')}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: getDiffColor(latest.observedDiff), fontWeight: 500 }}
                      >
                        {formatDiffBadge(latest.observedDiff, 'п.п.')}
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2, borderLeft: '4px solid #d32f2f' }}>
                      <Typography variant="caption" color="text.secondary">
                        Ожидаемая инфляция, 1 год
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {formatValue(latest.expected1y, '%')}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: getDiffColor(latest.expected1yDiff), fontWeight: 500 }}
                      >
                        {formatDiffBadge(latest.expected1yDiff, 'п.п.')}
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2, borderLeft: '4px solid #2e7d32' }}>
                      <Typography variant="caption" color="text.secondary">
                        Ожидаемая инфляция, 5 лет
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {formatValue(latest.expected5y, '%')}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: getDiffColor(latest.expected5yDiff), fontWeight: 500 }}
                      >
                        {formatDiffBadge(latest.expected5yDiff, 'п.п.')}
                      </Typography>
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2, borderLeft: '4px solid #ed6c02' }}>
                      <Typography variant="caption" color="text.secondary">
                        Разрыв (ожидания − набл.)
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {formatValue(latest.gap, ' п.п.')}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{ color: getDiffColor(latest.gapDiff), fontWeight: 500 }}
                      >
                        {formatDiffBadge(latest.gapDiff, 'п.п.')}
                      </Typography>
                    </Paper>
                  </Box>
                </Box>
              )}

              <Divider />

              {/* Upper Chart: Inflation Estimates (%) */}
              <Box>
                <Plot
                  data={upperChartData}
                  layout={{
                    title: {
                      text: 'Оценки инфляции населения (в %)',
                      font: { size: 16 },
                    },
                    xaxis: { title: 'Дата', automargin: true, gridcolor: '#f5f5f5' },
                    yaxis: {
                      title: 'Проценты (%)',
                      automargin: true,
                      tickformat: '.2f',
                      rangemode: 'normal',
                      autorange: true,
                      zeroline: false,
                      gridcolor: '#e0e0e0',
                    },
                    legend: { orientation: 'h', x: 0, y: 1.15 },
                    hovermode: 'x unified',
                    hoverlabel: { namelength: -1 },
                    margin: { l: 55, r: 40, t: 65, b: 40 },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: '100%', height: '520px' }}
                />
              </Box>

              <Divider />

              {/* Lower Chart: Gap (p.p.) */}
              <Box>
                <Plot
                  data={lowerChartData}
                  layout={{
                    title: {
                      text: 'Разрыв между годовой ожидаемой и наблюдаемой инфляцией (п.п.)',
                      font: { size: 16 },
                    },
                    xaxis: { title: 'Дата', automargin: true, gridcolor: '#f5f5f5' },
                    yaxis: {
                      title: 'Разрыв (п.п.)',
                      automargin: true,
                      tickformat: '.2f',
                      rangemode: 'normal',
                      autorange: true,
                      zeroline: true,
                      zerolinecolor: '#616161',
                      zerolinewidth: 2,
                      gridcolor: '#e0e0e0',
                    },
                    legend: { orientation: 'h', x: 0, y: 1.15 },
                    hovermode: 'x unified',
                    hoverlabel: { namelength: -1 },
                    margin: { l: 55, r: 40, t: 65, b: 40 },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: '100%', height: '440px' }}
                />
              </Box>

              <Divider />

              {/* Table of Recent Months */}
              {recentPoints.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{ fontWeight: 600, mb: 1, color: 'text.secondary' }}
                  >
                    Динамика за последние месяцы:
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: 'action.hover' }}>
                          <TableCell sx={{ fontWeight: 600 }}>Период</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            Наблюдаемая (%)
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            Ожидаемая, 1 год (%)
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            Ожидаемая, 5 лет (%)
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            Разрыв (п.п.)
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {recentPoints.map((row) => (
                          <TableRow key={row.recorddata} hover>
                            <TableCell>{row.formattedDate}</TableCell>
                            <TableCell align="right">
                              {formatValue(row.observed, '%')}
                              {row.observedDiff !== null && (
                                <Typography
                                  component="span"
                                  variant="caption"
                                  sx={{ ml: 1, color: getDiffColor(row.observedDiff) }}
                                >
                                  ({row.observedDiff > 0 ? '+' : ''}
                                  {row.observedDiff.toFixed(2)} п.п.)
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {formatValue(row.expected1y, '%')}
                              {row.expected1yDiff !== null && (
                                <Typography
                                  component="span"
                                  variant="caption"
                                  sx={{ ml: 1, color: getDiffColor(row.expected1yDiff) }}
                                >
                                  ({row.expected1yDiff > 0 ? '+' : ''}
                                  {row.expected1yDiff.toFixed(2)} п.п.)
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {formatValue(row.expected5y, '%')}
                              {row.expected5yDiff !== null && (
                                <Typography
                                  component="span"
                                  variant="caption"
                                  sx={{ ml: 1, color: getDiffColor(row.expected5yDiff) }}
                                >
                                  ({row.expected5yDiff > 0 ? '+' : ''}
                                  {row.expected5yDiff.toFixed(2)} п.п.)
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {formatValue(row.gap, ' п.п.')}
                              {row.gapDiff !== null && (
                                <Typography
                                  component="span"
                                  variant="caption"
                                  sx={{ ml: 1, color: getDiffColor(row.gapDiff) }}
                                >
                                  ({row.gapDiff > 0 ? '+' : ''}
                                  {row.gapDiff.toFixed(2)} п.п.)
                                </Typography>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Box>
              )}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};