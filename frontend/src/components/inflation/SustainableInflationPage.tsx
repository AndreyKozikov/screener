import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TablePagination,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import Plot from '../common/PlotlyScatterChart';
import {
  fetchSustainableInflationData,
  type SustainableInflationDataPoint,
} from '../../api/sustainableInflation';

type Period = 'year' | 'three-years' | 'all';

type IndicatorDefinition = {
  key: keyof Pick<
    SustainableInflationDataPoint,
    'trend_inflation_3y' | 'trend_inflation_5y' | 'modified_core_inflation'
  >;
  title: string;
  color: string;
};

const INDICATORS: IndicatorDefinition[] = [
  { key: 'trend_inflation_3y', title: 'Трендовая инфляция · 3 года', color: '#1976d2' },
  { key: 'trend_inflation_5y', title: 'Трендовая инфляция · 5 лет', color: '#e89318' },
  { key: 'modified_core_inflation', title: 'Модифицированная базовая инфляция', color: '#078d80' },
];

const parseIsoDate = (value: string): Date => new Date(value.slice(0, 10) + 'T00:00:00');

const formatIsoDate = (value: string): string => {
  const date = parseIsoDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

const formatMonth = (value: string): string => {
  const date = parseIsoDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
};

const formatValue = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatPercent = (value: number | null | undefined): string => {
  const formatted = formatValue(value);
  return formatted === '—' ? formatted : formatted + '%';
};

const formatChange = (value: number | null): string => {
  if (value == null || !Number.isFinite(value)) return 'Нет предыдущего значения';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return sign + formatValue(Math.abs(value)) + ' п.п. к предыдущему месяцу';
};

const getPeriodStart = (latestDate: string, period: Period): string | null => {
  if (period === 'all') return null;
  const date = parseIsoDate(latestDate);
  if (Number.isNaN(date.getTime())) return null;
  date.setMonth(date.getMonth() - (period === 'year' ? 11 : 35));
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-');
};

const SUMMARY_CARD_SX = {
  minWidth: 0,
  borderColor: '#d9e7fb',
  borderRadius: 2,
  background: 'linear-gradient(145deg, rgba(255,255,255,0.82), rgba(242,247,255,0.76))',
  boxShadow: '0 2px 8px rgba(30, 81, 145, 0.06)',
};

const RUSSIAN_PLOTLY_LOCALES = {
  ru: {
    format: {
      months: [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
      ],
      shortMonths: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
    },
  },
};

export const SustainableInflationPage: React.FC = () => {
  const [data, setData] = useState<SustainableInflationDataPoint[]>([]);
  const [period, setPeriod] = useState<Period>('year');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void fetchSustainableInflationData()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((requestError: unknown) => {
        console.error('Error fetching sustainable inflation data:', requestError);
        if (active) setError('Не удалось загрузить данные устойчивой инфляции');
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const sortedData = useMemo(
    () => [...data].sort((left, right) => left.record_date.localeCompare(right.record_date)),
    [data],
  );
  const latest = sortedData.at(-1) ?? null;
  const previous = sortedData.at(-2) ?? null;

  const visibleRows = useMemo(() => {
    if (!latest) return [];
    const startDate = getPeriodStart(latest.record_date, period);
    return sortedData
      .filter((row) => !startDate || row.record_date >= startDate)
      .reverse();
  }, [latest, period, sortedData]);

  const pageRows = useMemo(
    () => visibleRows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [page, rowsPerPage, visibleRows],
  );

  const chartData = useMemo(() => {
    const chronologicalRows = [...visibleRows].reverse();
    const dates = chronologicalRows.map((row) => row.record_date);
    return [
      {
        x: dates,
        y: chronologicalRows.map((row) => row.trend_inflation_3y),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Трендовая инфляция · 3 года',
        line: { color: '#1976d2', width: 2.5 },
        marker: { color: '#1976d2', size: 5 },
        hovertemplate: '%{x|%b %Y}<br>Тренд, 3 года: <b>%{y:.2f}%</b><extra></extra>',
      },
      {
        x: dates,
        y: chronologicalRows.map((row) => row.trend_inflation_5y),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Трендовая инфляция · 5 лет',
        line: { color: '#e89318', width: 2.5 },
        marker: { color: '#e89318', size: 5 },
        hovertemplate: '%{x|%b %Y}<br>Тренд, 5 лет: <b>%{y:.2f}%</b><extra></extra>',
      },
      {
        x: dates,
        y: chronologicalRows.map((row) => row.modified_core_inflation),
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Модифицированная базовая инфляция',
        yaxis: 'y2',
        line: { color: '#078d80', width: 2.5 },
        marker: { color: '#078d80', size: 5 },
        hovertemplate: '%{x|%b %Y}<br>Модифицированная базовая: <b>%{y:.2f}%</b><extra></extra>',
      },
    ];
  }, [visibleRows]);

  const displayRange = useMemo(() => {
    if (!visibleRows.length) return null;
    return {
      from: visibleRows[visibleRows.length - 1].record_date,
      till: visibleRows[0].record_date,
    };
  }, [visibleRows]);

  const handlePeriodChange = (_event: React.MouseEvent<HTMLElement>, nextPeriod: Period | null) => {
    if (!nextPeriod) return;
    setPeriod(nextPeriod);
    setPage(0);
  };

  return (
    <Box
      sx={{
        width: '100%',
        minWidth: 0,
        minHeight: 0,
        p: { xs: 1, sm: 2 },
        background: 'linear-gradient(135deg, rgba(243,248,255,0.72) 0%, rgba(255,255,255,0.55) 56%, rgba(245,249,255,0.72) 100%)',
        borderRadius: 2,
      }}
    >
      <Stack spacing={{ xs: 1.25, sm: 1.75 }}>
        <Paper
          variant="outlined"
          sx={{
            px: { xs: 1.25, sm: 2 },
            py: { xs: 1.25, sm: 1.5 },
            borderRadius: 2,
            borderColor: '#dce8f8',
            background: 'linear-gradient(145deg, rgba(255,255,255,0.82), rgba(246,250,255,0.72))',
            boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)',
          }}
        >
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography
                component="h1"
                sx={{ color: '#102b50', fontWeight: 750, fontSize: { xs: '1.05rem', sm: '1.35rem' } }}
              >
                Устойчивая инфляция
              </Typography>
              <Typography sx={{ mt: 0.35, color: '#607693', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>
                Трендовые оценки и модифицированный показатель базовой инфляции
              </Typography>
            </Box>
            {latest && (
              <Stack direction="row" alignItems="center" spacing={0.5} sx={{ color: '#607693', flexShrink: 0 }}>
                <CalendarMonthOutlinedIcon sx={{ fontSize: 17 }} />
                <Typography sx={{ fontSize: { xs: '0.7rem', sm: '0.78rem' } }}>
                  Последний период: {formatMonth(latest.record_date)}
                </Typography>
              </Stack>
            )}
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1.5,
            flexWrap: 'wrap',
            px: { xs: 1, sm: 1.5 },
            py: 1,
            borderRadius: 2,
            borderColor: '#dce8f8',
            background: 'rgba(255,255,255,0.62)',
          }}
        >
          <ToggleButtonGroup
            exclusive
            size="small"
            value={period}
            onChange={handlePeriodChange}
            aria-label="Период истории устойчивой инфляции"
            sx={{
              '& .MuiToggleButton-root': {
                px: { xs: 1.1, sm: 1.75 },
                py: 0.55,
                borderColor: '#d9e7fb',
                color: '#365477',
                fontSize: { xs: '0.7rem', sm: '0.78rem' },
                textTransform: 'none',
              },
              '& .MuiToggleButton-root.Mui-selected': {
                color: '#fff',
                bgcolor: '#1769e8',
                borderColor: '#1769e8',
              },
              '& .MuiToggleButton-root.Mui-selected:hover': { bgcolor: '#155fcf' },
            }}
          >
            <ToggleButton value="year">1 год</ToggleButton>
            <ToggleButton value="three-years">3 года</ToggleButton>
            <ToggleButton value="all">Весь период</ToggleButton>
          </ToggleButtonGroup>
          <Typography sx={{ color: '#607693', fontSize: { xs: '0.68rem', sm: '0.76rem' } }}>
            {isLoading
              ? 'Загрузка периода…'
              : displayRange
              ? formatIsoDate(displayRange.from) + ' — ' + formatIsoDate(displayRange.till)
              : 'Нет наблюдений за выбранный период'}
          </Typography>
        </Paper>

        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={28} aria-label="Загрузка данных устойчивой инфляции" />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {!isLoading && !error && latest && (
          <>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' },
                gap: { xs: 0.85, sm: 1.25 },
              }}
            >
              {INDICATORS.map((indicator) => {
                const value = latest[indicator.key];
                const previousValue = previous?.[indicator.key] ?? null;
                const change = value != null && previousValue != null ? value - previousValue : null;
                return (
                  <Card
                    key={indicator.key}
                    variant="outlined"
                    sx={{
                      ...SUMMARY_CARD_SX,
                      borderLeft: '3px solid ' + indicator.color,
                    }}
                  >
                    <CardContent sx={{ p: { xs: 1.2, sm: 1.6 }, '&:last-child': { pb: { xs: 1.2, sm: 1.6 } } }}>
                      <Typography
                        sx={{
                          minHeight: { sm: '2.2em' },
                          color: '#365477',
                          fontSize: { xs: '0.72rem', sm: '0.78rem' },
                          lineHeight: 1.25,
                        }}
                      >
                        {indicator.title}
                      </Typography>
                      <Typography
                        sx={{
                          mt: 0.6,
                          color: '#122d51',
                          fontSize: { xs: '1.2rem', sm: '1.45rem' },
                          lineHeight: 1.05,
                          fontWeight: 750,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {formatPercent(value)}
                      </Typography>
                      <Typography sx={{ mt: 0.55, color: '#607693', fontSize: { xs: '0.66rem', sm: '0.72rem' } }}>
                        {formatChange(change)}
                      </Typography>
                    </CardContent>
                  </Card>
                );
              })}
            </Box>

            <Paper
              variant="outlined"
              sx={{
                minWidth: 0,
                overflow: 'hidden',
                borderRadius: 2,
                borderColor: '#dce8f8',
                background: 'linear-gradient(145deg, rgba(255,255,255,0.8), rgba(255,255,255,0.62))',
                boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)',
              }}
            >
              <Box
                sx={{
                  px: { xs: 1.25, sm: 2 },
                  pt: 1.35,
                  pb: 0.25,
                }}
              >
                <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '0.9rem' }}>
                  Динамика показателей
                </Typography>
                <Typography sx={{ mt: 0.25, color: '#71839d', fontSize: '0.72rem' }}>
                  Трендовые оценки — левая шкала; модифицированная базовая инфляция — правая
                </Typography>
              </Box>
              <Box sx={{ px: { xs: 0.5, sm: 1.25 }, pb: 0.5, minWidth: 0 }}>
                <Plot
                  data={chartData}
                  layout={{
                    autosize: true,
                    separators: ', ',
                    xaxis: {
                      type: 'date',
                      tickformat: '%b %Y',
                      dtick: period === 'all' ? 'M12' : period === 'three-years' ? 'M6' : 'M3',
                      automargin: true,
                      showgrid: true,
                      gridcolor: '#e9f0fa',
                      zeroline: false,
                      ticks: 'outside',
                      tickfont: { size: 12, color: '#56708f' },
                      title: { text: 'Период', font: { size: 12, color: '#56708f' } },
                    },
                    yaxis: {
                      title: { text: 'Трендовая инфляция, %', font: { size: 12, color: '#56708f' } },
                      ticksuffix: '%',
                      automargin: true,
                      gridcolor: '#e9f0fa',
                      zeroline: false,
                      ticks: 'outside',
                      tickfont: { size: 12, color: '#56708f' },
                    },
                    yaxis2: {
                      title: { text: 'Модифицированная базовая, %', font: { size: 12, color: '#56708f' } },
                      overlaying: 'y',
                      side: 'right',
                      rangemode: 'tozero',
                      ticksuffix: '%',
                      automargin: true,
                      showgrid: false,
                      zeroline: false,
                      ticks: 'outside',
                      tickfont: { size: 12, color: '#56708f' },
                    },
                    showlegend: true,
                    legend: {
                      orientation: 'h',
                      x: 0,
                      y: 1.15,
                      font: { size: 11, color: '#365477' },
                    },
                    hovermode: 'x unified',
                    hoverlabel: { font: { size: 13 } },
                    margin: { l: 62, r: 70, t: 36, b: 52 },
                    plot_bgcolor: 'rgba(255,255,255,0)',
                    paper_bgcolor: 'rgba(255,255,255,0)',
                  }}
                  config={{
                    responsive: true,
                    displayModeBar: true,
                    scrollZoom: false,
                    displaylogo: false,
                    locale: 'ru',
                    locales: RUSSIAN_PLOTLY_LOCALES,
                  }}
                  style={{ width: '100%', height: 'clamp(290px, 38vw, 390px)' }}
                />
              </Box>
            </Paper>

            <Paper
              variant="outlined"
              sx={{
                overflow: 'hidden',
                borderRadius: 2,
                borderColor: '#dce8f8',
                background: 'linear-gradient(145deg, rgba(255,255,255,0.78), rgba(255,255,255,0.61))',
                boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)',
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: { xs: 'flex-start', sm: 'center' },
                  justifyContent: 'space-between',
                  flexDirection: { xs: 'column', sm: 'row' },
                  gap: 0.5,
                  px: { xs: 1.25, sm: 2 },
                  py: 1.25,
                  borderBottom: '1px solid #e3ecf8',
                }}
              >
                <Box>
                  <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '0.9rem' }}>
                    История значений
                  </Typography>
                  <Typography sx={{ mt: 0.25, color: '#71839d', fontSize: '0.72rem' }}>
                    Значения по месяцам, в процентах
                  </Typography>
                </Box>
                <Typography sx={{ color: '#71839d', fontSize: '0.72rem' }}>
                  {visibleRows.length} наблюдений
                </Typography>
              </Box>

              {visibleRows.length ? (
                <>
                  <TableContainer sx={{ overflowX: 'auto' }}>
                    <Table size="small" aria-label="История показателей устойчивой инфляции">
                      <TableHead>
                        <TableRow
                          sx={{
                            '& .MuiTableCell-root': {
                              py: 1.1,
                              color: '#4a6385',
                              bgcolor: 'rgba(247,250,255,0.82)',
                              borderColor: '#e3ecf8',
                              fontSize: { xs: '0.68rem', sm: '0.76rem' },
                              fontWeight: 650,
                              lineHeight: 1.25,
                            },
                          }}
                        >
                          <TableCell sx={{ minWidth: 125 }}>Период</TableCell>
                          <TableCell align="right" sx={{ minWidth: 145 }}>
                            Трендовая инфляция · 3 года, %
                          </TableCell>
                          <TableCell align="right" sx={{ minWidth: 145 }}>
                            Трендовая инфляция · 5 лет, %
                          </TableCell>
                          <TableCell align="right" sx={{ minWidth: 185 }}>
                            Модифицированная базовая инфляция, %
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {pageRows.map((row, rowIndex) => (
                          <TableRow
                            key={row.record_date}
                            hover
                            sx={{
                              bgcolor: rowIndex === 0 && page === 0
                                ? 'rgba(238,246,255,0.58)'
                                : rowIndex % 2 === 1
                                  ? 'rgba(250,252,255,0.38)'
                                  : undefined,
                              '& .MuiTableCell-root': {
                                py: 0.9,
                                color: '#29476f',
                                borderColor: 'rgba(226,235,246,0.88)',
                                fontSize: { xs: '0.72rem', sm: '0.8rem' },
                                fontVariantNumeric: 'tabular-nums',
                              },
                            }}
                          >
                            <TableCell sx={{ color: '#415d7d', fontWeight: 550 }}>
                              {formatMonth(row.record_date)}
                            </TableCell>
                            <TableCell align="right">{formatValue(row.trend_inflation_3y)}</TableCell>
                            <TableCell align="right">{formatValue(row.trend_inflation_5y)}</TableCell>
                            <TableCell align="right">{formatValue(row.modified_core_inflation)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  <TablePagination
                    component="div"
                    count={visibleRows.length}
                    page={page}
                    onPageChange={(_event, nextPage) => setPage(nextPage)}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={(event) => {
                      setRowsPerPage(Number(event.target.value));
                      setPage(0);
                    }}
                    rowsPerPageOptions={[12, 24, 48]}
                    labelRowsPerPage="Строк:"
                    labelDisplayedRows={({ from, to, count }) => from + '–' + to + ' из ' + count}
                    sx={{
                      color: '#607693',
                      '& .MuiTablePagination-toolbar': { minHeight: 44, px: { xs: 0.5, sm: 2 } },
                      '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': {
                        fontSize: '0.72rem',
                      },
                    }}
                  />
                </>
              ) : (
                <Box sx={{ px: 2, py: 4, textAlign: 'center' }}>
                  <Typography sx={{ color: '#71839d', fontSize: '0.82rem' }}>
                    Нет данных за выбранный период
                  </Typography>
                </Box>
              )}

              <Divider />
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                justifyContent="space-between"
                spacing={0.4}
                sx={{ px: { xs: 1.25, sm: 2 }, py: 1, color: '#7a8ca5' }}
              >
                <Typography sx={{ fontSize: '0.68rem' }}>Источник: база данных приложения</Typography>
                <Typography sx={{ fontSize: '0.68rem' }}>
                  {sortedData.length} месячных наблюдений
                  {sortedData.length > 0
                    ? ' · ' + formatMonth(sortedData[0].record_date) + ' — ' + formatMonth(sortedData[sortedData.length - 1].record_date)
                    : ''}
                </Typography>
              </Stack>
            </Paper>
          </>
        )}

        {!isLoading && !error && !latest && (
          <Alert severity="info">В базе пока нет данных устойчивой инфляции</Alert>
        )}
      </Stack>
    </Box>
  );
};
