import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Paper,
  Popover,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import DescriptionIcon from '@mui/icons-material/Description';
import DownloadIcon from '@mui/icons-material/Download';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { type Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import Plot from 'react-plotly.js';
import {
  downloadZerocuponJson,
  downloadZerocuponMarkdown,
  fetchZerocuponData,
  type ZerocuponRecord,
} from '../../api/zerocupon';
import { YieldCurveSpreads } from './YieldCurveSpreads';

const POPULAR_TERMS = new Set([1, 3, 5, 10]);
const SERIES_COLORS = [
  '#90a4ae', '#78909c', '#546e7a', '#1976d2', '#5e35b1', '#00897b',
  '#ed6c02', '#2e7d32', '#e53935', '#8e24aa', '#3949ab',
];

dayjs.extend(customParseFormat);
dayjs.locale('ru');

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

const formatDateToString = (date: Dayjs | null): string | null => (
  date?.isValid() ? date.format('DD.MM.YYYY') : null
);

const dateToIso = (value: string): string => {
  const parsed = dayjs(value, 'DD.MM.YYYY', true);
  return parsed.isValid() ? parsed.format('YYYY-MM-DD') : value.slice(0, 10);
};

const formatDate = (value: string | null | undefined): string => {
  if (!value) return '—';
  const parsed = dayjs(value, 'DD.MM.YYYY', true);
  return parsed.isValid() ? parsed.format('DD.MM.YYYY') : value;
};

const formatPercent = (value: string | number | null | undefined): string => {
  if (value == null || value === '') return '—';
  const numeric = typeof value === 'number' ? value : Number(value.replace(',', '.'));
  return Number.isFinite(numeric)
    ? numeric.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%'
    : '—';
};

const getTerm = (field: string): number | null => {
  const match = field.match(/Срок\s+(\d+(?:\.\d+)?)\s+лет/);
  return match ? Number(match[1]) : null;
};

const getNumericValue = (value: string | number | null | undefined): number | null => {
  if (value == null || value === '') return null;
  const numeric = typeof value === 'number' ? value : Number(value.trim().replace(',', '.'));
  return Number.isFinite(numeric) ? numeric : null;
};

const formatTerm = (term: number): string => {
  if (term === 0.25) return '3 месяца';
  if (term === 0.5) return '6 месяцев';
  if (term === 0.75) return '9 месяцев';
  const unit = term === 1 ? 'год' : term >= 2 && term <= 4 ? 'года' : 'лет';
  return `${term.toLocaleString('ru-RU')} ${unit}`;
};

const sortByDateAndTime = (left: ZerocuponRecord, right: ZerocuponRecord): number => {
  const dateOrder = dateToIso(left.Дата).localeCompare(dateToIso(right.Дата));
  return dateOrder || (left.Время ?? '').localeCompare(right.Время ?? '');
};

const SUMMARY_CARD_SX = {
  minWidth: 0,
  borderColor: '#d9e7fb',
  borderRadius: 2,
  background: 'linear-gradient(145deg, rgba(255,255,255,0.9), rgba(242,247,255,0.82))',
  boxShadow: '0 2px 8px rgba(30, 81, 145, 0.06)',
};

/** История и график кривой бескупонной доходности. */
export const ZerocuponTable: React.FC = () => {
  const [data, setData] = useState<ZerocuponRecord[]>([]);
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(() => dayjs().subtract(1, 'year'));
  const [dateTo, setDateTo] = useState<Dayjs | null>(() => dayjs().subtract(1, 'day'));
  const [filterAnchor, setFilterAnchor] = useState<HTMLElement | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (from: Dayjs | null, till: Dayjs | null) => {
    const fromString = formatDateToString(from);
    const tillString = formatDateToString(till);
    if (!fromString || !tillString) return;

    try {
      setLoading(true);
      setError(null);
      const response = await fetchZerocuponData(fromString, tillString);
      setData([...response.data].sort(sortByDateAndTime));
      setPage(0);
    } catch (requestError: unknown) {
      console.error('Error fetching zero-coupon yield curve data:', requestError);
      setError('Не удалось загрузить данные кривой бескупонной доходности');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData(dayjs().subtract(1, 'year'), dayjs().subtract(1, 'day'));
  }, [loadData]);

  const periodFields = useMemo(() => {
    const fields = new Set<string>();
    data.forEach((row) => Object.keys(row).forEach((field) => {
      if (field !== 'Дата' && field !== 'Время' && getTerm(field) !== null) fields.add(field);
    }));
    return [...fields].sort((left, right) => (getTerm(left) ?? 0) - (getTerm(right) ?? 0));
  }, [data]);

  const chartData = useMemo(() => periodFields.map((field, index) => {
    const term = getTerm(field)!;
    const color = SERIES_COLORS[index % SERIES_COLORS.length];
    const name = formatTerm(term);
    return {
      x: data.map((row) => dateToIso(row.Дата)),
      y: data.map((row) => getNumericValue(row[field])),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name,
      visible: POPULAR_TERMS.has(term) ? true : 'legendonly' as const,
      line: { color, width: POPULAR_TERMS.has(term) ? 2.5 : 1.8 },
      marker: { color, size: POPULAR_TERMS.has(term) ? 4 : 3 },
      hovertemplate: `%{x|%d.%m.%Y}<br>${name}: <b>%{y:.2f}%</b><extra></extra>`,
      connectgaps: false,
    };
  }), [data, periodFields]);

  const latestRecord = useMemo(() => data.at(-1) ?? null, [data]);
  const visibleRows = useMemo(
    () => [...data].reverse().slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [data, page, rowsPerPage],
  );

  const handleApplyFilter = () => {
    if (!dateFrom || !dateTo) return;
    void loadData(dateFrom, dateTo);
    setFilterAnchor(null);
  };

  const handleResetFilter = () => {
    const from = dayjs().subtract(1, 'year');
    const till = dayjs().subtract(1, 'day');
    setDateFrom(from);
    setDateTo(till);
    void loadData(from, till);
    setFilterAnchor(null);
  };

  const handleDownloadJson = async () => {
    try {
      await downloadZerocuponJson(formatDateToString(dateFrom), formatDateToString(dateTo));
    } catch (requestError: unknown) {
      console.error('Error downloading zero-coupon JSON:', requestError);
      setError('Не удалось скачать JSON');
    }
  };

  const handleDownloadMarkdown = async () => {
    try {
      await downloadZerocuponMarkdown(formatDateToString(dateFrom), formatDateToString(dateTo));
    } catch (requestError: unknown) {
      console.error('Error downloading zero-coupon Markdown:', requestError);
      setError('Не удалось скачать Markdown');
    }
  };

  return (
    <Box sx={{
      width: '100%',
      minWidth: 0,
      p: { xs: 1, sm: 2 },
      background: 'linear-gradient(135deg, #f3f8ff 0%, #ffffff 56%, #f5f9ff 100%)',
      borderRadius: 2,
    }}>
      <Stack spacing={{ xs: 1.25, sm: 1.75 }}>
        <Paper variant="outlined" sx={{
          px: { xs: 1.25, sm: 2 },
          py: { xs: 1, sm: 1.25 },
          borderRadius: 2,
          borderColor: '#dce8f8',
          boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)',
        }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            justifyContent="space-between"
            spacing={1}
          >
            <Box>
              <Typography variant="h5" sx={{ color: '#102b50', fontWeight: 750, fontSize: { xs: '1.05rem', sm: '1.35rem' } }}>
                Кривая бескупонной доходности
              </Typography>
              <Typography sx={{ mt: 0.25, color: '#607693', fontSize: '0.75rem' }}>
                Доходность ОФЗ по срокам до погашения, % годовых
              </Typography>
            </Box>
            <Stack direction="row" alignItems="center" spacing={0.5} flexWrap="wrap">
              <Typography variant="caption" sx={{ color: '#607693', fontSize: { xs: '0.62rem', sm: '0.7rem' } }}>
                Дата данных: {formatDate(latestRecord?.Дата)}
              </Typography>
              <Tooltip title="Фильтр периода">
                <IconButton
                  aria-label="Фильтр периода"
                  size="small"
                  onClick={(event) => setFilterAnchor(event.currentTarget)}
                  sx={{ color: '#6b83a3', p: 0.5 }}
                >
                  <CalendarMonthOutlinedIcon sx={{ fontSize: 17 }} />
                </IconButton>
              </Tooltip>
            </Stack>
          </Stack>
          <Stack direction="row" spacing={0.75} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
            <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={() => void handleDownloadJson()} disabled={loading || data.length === 0}>
              Скачать JSON
            </Button>
            <Button size="small" variant="outlined" startIcon={<DescriptionIcon />} onClick={() => void handleDownloadMarkdown()} disabled={loading || data.length === 0}>
              Скачать Markdown
            </Button>
            <Typography variant="caption" sx={{ alignSelf: 'center', ml: 'auto', color: '#71839d' }}>
              {data.length} наблюдений
            </Typography>
          </Stack>
        </Paper>

        <Popover
          open={Boolean(filterAnchor)}
          anchorEl={filterAnchor}
          onClose={() => setFilterAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="ru">
            <Stack spacing={1.5} sx={{ p: 2, width: { xs: 280, sm: 360 } }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Период графика и таблицы</Typography>
              <DatePicker label="С даты" value={dateFrom} onChange={setDateFrom} maxDate={dateTo ?? undefined} format="DD.MM.YYYY" slotProps={{ textField: { size: 'small' } }} />
              <DatePicker label="По дату" value={dateTo} onChange={setDateTo} minDate={dateFrom ?? undefined} format="DD.MM.YYYY" slotProps={{ textField: { size: 'small' } }} />
              <Stack direction="row" justifyContent="space-between">
                <Button size="small" onClick={handleResetFilter}>Последний год</Button>
                <Button size="small" variant="contained" onClick={handleApplyFilter} disabled={!dateFrom || !dateTo}>Применить</Button>
              </Stack>
            </Stack>
          </LocalizationProvider>
        </Popover>

        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}><CircularProgress /></Box>}
        {error && <Alert severity="error">{error}</Alert>}

        {!loading && !error && (
          <>
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))', md: 'repeat(5, minmax(0, 1fr))' },
              gap: { xs: 0.75, sm: 1.25 },
            }}>
              {[1, 2, 3, 5, 10].map((term) => {
                const field = periodFields.find((candidate) => getTerm(candidate) === term);
                return (
                  <Card key={term} variant="outlined" sx={SUMMARY_CARD_SX}>
                    <CardContent sx={{ p: { xs: 1, sm: 1.5 }, '&:last-child': { pb: { xs: 1, sm: 1.5 } } }}>
                      <Typography variant="caption" sx={{ display: 'block', color: '#365477', lineHeight: 1.15, fontSize: { xs: '0.64rem', sm: '0.76rem' } }}>
                        Срок {formatTerm(term)}
                      </Typography>
                      <Typography sx={{ mt: 0.65, color: '#122d51', fontWeight: 750, lineHeight: 1.05, fontSize: { xs: '1rem', sm: '1.3rem' } }}>
                        {field && latestRecord ? formatPercent(latestRecord[field]) : '—'}
                      </Typography>
                    </CardContent>
                  </Card>
                );
              })}
            </Box>

            <YieldCurveSpreads records={data} />

            <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden', borderColor: '#dce8f8', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
              <Box sx={{ px: { xs: 1.25, sm: 2 }, pt: 1.25, pb: 0.25 }}>
                <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '0.9rem' }}>Динамика доходности</Typography>
                <Typography sx={{ mt: 0.25, color: '#71839d', fontSize: '0.72rem' }}>
                  Сроки 1, 3, 5 и 10 лет включены; остальные можно включить в легенде
                </Typography>
              </Box>
              {chartData.length ? (
                <Box sx={{ px: { xs: 0.5, sm: 1.25 }, pb: 0.5, minWidth: 0 }}>
                  <Plot
                    data={chartData}
                    layout={{
                      autosize: true,
                      separators: ', ',
                      xaxis: {
                        type: 'date',
                        tickformat: '%b %Y',
                        dtick: 'M2',
                        hoverformat: '%d.%m.%Y',
                        automargin: true,
                        showgrid: true,
                        gridcolor: '#e9f0fa',
                        zeroline: false,
                        ticks: 'outside',
                        tickfont: { size: 12, color: '#56708f' },
                      },
                      yaxis: {
                        title: { text: 'Доходность, % годовых', font: { size: 12, color: '#56708f' } },
                        ticksuffix: '%',
                        automargin: true,
                        gridcolor: '#e9f0fa',
                        zeroline: false,
                        ticks: 'outside',
                        tickfont: { size: 12, color: '#56708f' },
                      },
                      showlegend: true,
                      legend: { orientation: 'h', x: 0, y: 1.15, font: { size: 11, color: '#365477' } },
                      hovermode: 'x unified',
                      hoverlabel: { font: { size: 13 } },
                      margin: { l: 58, r: 12, t: 38, b: 42 },
                      plot_bgcolor: 'rgba(255,255,255,0)',
                      paper_bgcolor: 'rgba(255,255,255,0)',
                    }}
                    config={{ responsive: true, displayModeBar: true, scrollZoom: false, displaylogo: false, locale: 'ru', locales: RUSSIAN_PLOTLY_LOCALES }}
                    style={{ width: '100%', height: 'clamp(290px, 42vw, 430px)' }}
                  />
                </Box>
              ) : (
                <Typography color="text.secondary" sx={{ p: 3, textAlign: 'center', fontSize: '0.8rem' }}>
                  Нет данных за выбранный период
                </Typography>
              )}
            </Paper>

            <Paper variant="outlined" sx={{ overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.82), rgba(246,250,255,0.72))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={0.4} sx={{ px: { xs: 1.25, sm: 2 }, py: 1.25, borderBottom: '1px solid #e3ecf8' }}>
                <Box>
                  <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '0.9rem' }}>История значений</Typography>
                  <Typography sx={{ mt: 0.25, color: '#71839d', fontSize: '0.72rem' }}>Доходность по срокам, в процентах годовых</Typography>
                </Box>
                <Typography sx={{ color: '#71839d', fontSize: '0.72rem', alignSelf: { xs: 'flex-start', sm: 'center' } }}>
                  {data.length} наблюдений
                </Typography>
              </Stack>
              {data.length ? (
                <>
                  <TableContainer sx={{ overflowX: 'auto' }}>
                    <Table size="small" aria-label="История кривой бескупонной доходности" sx={{ minWidth: 760 }}>
                      <TableHead>
                        <TableRow sx={{ '& .MuiTableCell-root': { py: 1.1, color: '#4a6385', bgcolor: 'rgba(247,250,255,0.82)', borderColor: '#e3ecf8', fontSize: '0.74rem', fontWeight: 650, whiteSpace: 'nowrap' } }}>
                          <TableCell>Дата</TableCell>
                          {periodFields.map((field) => <TableCell key={field} align="right">{formatTerm(getTerm(field)!)}</TableCell>)}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {visibleRows.map((row, rowIndex) => (
                          <TableRow key={`${row.Дата}-${row.Время ?? ''}-${rowIndex}`} hover sx={{ bgcolor: rowIndex % 2 === 1 ? 'rgba(250,252,255,0.55)' : undefined, '& .MuiTableCell-root': { py: 0.85, color: '#29476f', borderColor: 'rgba(226,235,246,0.88)', fontSize: '0.78rem', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' } }}>
                            <TableCell sx={{ color: '#415d7d', fontWeight: 550 }}>{formatDate(row.Дата)}</TableCell>
                            {periodFields.map((field) => <TableCell key={field} align="right">{formatPercent(row[field])}</TableCell>)}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                  <TablePagination
                    component="div"
                    count={data.length}
                    page={page}
                    onPageChange={(_event, nextPage) => setPage(nextPage)}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
                    rowsPerPageOptions={[12, 24, 48]}
                    labelRowsPerPage="Строк:"
                    labelDisplayedRows={({ from, to, count }) => `${from}–${to} из ${count}`}
                    sx={{ color: '#607693', '& .MuiTablePagination-toolbar': { minHeight: 44, px: { xs: 0.5, sm: 2 } }, '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': { fontSize: '0.72rem' } }}
                  />
                </>
              ) : (
                <Box sx={{ px: 2, py: 4, textAlign: 'center' }}>
                  <Typography sx={{ color: '#71839d', fontSize: '0.82rem' }}>Нет данных за выбранный период</Typography>
                </Box>
              )}
              <Box sx={{ px: { xs: 1.25, sm: 2 }, py: 1, color: '#7a8ca5', borderTop: '1px solid rgba(226,235,246,0.88)' }}>
                <Typography sx={{ fontSize: '0.68rem' }}>Источник: Московская биржа · {data.length} дневных наблюдений</Typography>
              </Box>
            </Paper>
          </>
        )}
      </Stack>
    </Box>
  );
};
