import React, { useEffect, useMemo, useState } from 'react';
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
  TableSortLabel,
  Tabs,
  Tab,
  Tooltip,
  Typography,
} from '@mui/material';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { type Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import Plot from 'react-plotly.js';
import { fetchIpcDashboardData } from '../../api/ipcDataApi';
import type { IpcDashboardData, IpcMonthlyPoint, IpcWeeklyPoint } from '../../types/ipcData';

const russianPlotlyLocales = {
  ru: {
    format: {
      months: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
      shortMonths: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
    },
  },
};

const formatDate = (value: string | null | undefined): string => {
  if (!value) return '—';
  const parsed = new Date(value.slice(0, 10) + 'T00:00:00');
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('ru-RU');
};

const formatMonth = (value: string | null | undefined): string => {
  if (!value) return '—';
  const parsed = new Date(value.slice(0, 10) + 'T00:00:00');
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' });
};

const formatNumber = (value: number | null | undefined): string => (
  value == null || !Number.isFinite(value)
    ? '—'
    : value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
);

const formatPercent = (value: number | null | undefined, signed = false): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  const sign = signed && value > 0 ? '+' : '';
  return sign + formatNumber(value) + '%';
};

const formatChange = (value: number | null | undefined, unit: '%' | 'п.п.'): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  const arrow = value > 0 ? '▲ ' : value < 0 ? '▼ ' : '• ';
  const sign = value > 0 ? '+' : '';
  return arrow + sign + formatNumber(value) + (unit === '%' ? '%' : ' ' + unit);
};

// For CPI/inflation a decrease is positive (green), an increase is negative (red).
const changeColor = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value) || Math.abs(value) < 0.005) return '#8292a8';
  return value < 0 ? '#079669' : '#e5485d';
};

const formatSignedNumber = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value)) return '—';
  return (value > 0 ? '+' : '') + formatNumber(value);
};

interface TableColumn<T> {
  key: keyof T;
  label: string;
  align?: 'left' | 'right';
  render: (row: T) => React.ReactNode;
}

function HistoryTable<T extends object>({
  title,
  rows,
  columns,
  rowKey,
}: {
  title: string;
  rows: T[];
  columns: TableColumn<T>[];
  rowKey: (row: T) => string;
}) {
  const [sort, setSort] = useState<{ key: keyof T; descending: boolean } | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(5);

  useEffect(() => setPage(0), [rows]);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const left = a[sort.key];
      const right = b[sort.key];
      if (left == null) return right == null ? 0 : 1;
      if (right == null) return -1;
      const comparison = typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right));
      return sort.descending ? -comparison : comparison;
    });
  }, [rows, sort]);

  const visibleRows = sortedRows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <Paper variant="outlined" sx={{ minWidth: 0, overflow: 'hidden', borderColor: '#dce8f8', borderRadius: 2, boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
      <Typography variant="subtitle2" sx={{ px: 1.25, py: 1, fontWeight: 700, color: '#16345e', bgcolor: '#f6f9fe', borderBottom: '1px solid #e3ecf8', fontSize: '0.82rem' }}>
        {title}
      </Typography>
      <TableContainer sx={{ overflowX: 'auto', maxHeight: 420 }}>
        <Table size="small" stickyHeader sx={{
          width: '100%',
          tableLayout: 'fixed',
          '& .MuiTableCell-root': { px: 0.45, py: 0.6, fontSize: '0.78rem', textAlign: 'center !important', verticalAlign: 'middle', borderColor: '#edf2f9', color: '#1d3557' },
          '& .MuiTableCell-head': { whiteSpace: 'normal', overflowWrap: 'anywhere', lineHeight: 1.15, bgcolor: '#f7faff', color: '#4a6385', fontWeight: 600, fontSize: '0.72rem' },
          '& .MuiTableBody-root .MuiTableCell-root': { whiteSpace: 'nowrap' },
          '& .MuiTableBody-root .MuiTableRow-root:nth-of-type(even)': { bgcolor: '#fbfdff' },
        }}>
          <TableHead>
            <TableRow>
              {columns.map((column, index) => (
                <TableCell key={String(column.key) + '-' + index} align="center">
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%' }}>
                    <TableSortLabel
                      active={sort?.key === column.key}
                      direction={sort?.key === column.key && sort.descending ? 'desc' : 'asc'}
                      onClick={() => setSort((current) => ({
                        key: column.key,
                        descending: current?.key === column.key ? !current.descending : false,
                      }))}
                      sx={{
                        fontSize: 'inherit',
                        lineHeight: 1.2,
                        justifyContent: 'center',
                        textAlign: 'center',
                        '& .MuiTableSortLabel-icon': { mx: 0.25 },
                      }}
                    >
                      {column.label}
                    </TableSortLabel>
                  </Box>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleRows.map((row) => (
              <TableRow key={rowKey(row)} hover>
                {columns.map((column, index) => (
                  <TableCell key={String(column.key) + '-' + index} align="center">
                    {column.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
            {visibleRows.length === 0 && (
              <TableRow><TableCell colSpan={columns.length} align="center">Нет данных за выбранный период</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={sortedRows.length}
          page={page}
          onPageChange={(_event, nextPage) => setPage(nextPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(event) => {
            setRowsPerPage(Number(event.target.value));
            setPage(0);
          }}
          rowsPerPageOptions={[5, 10, 25]}
          labelRowsPerPage="Строк:"
          sx={{
            minHeight: 42,
            '& .MuiTablePagination-toolbar': { minHeight: 42, pl: 1, pr: 0.5 },
            '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': { fontSize: '0.8rem' },
            '& .MuiTablePagination-select': { fontSize: '0.8rem' },
            '& .MuiTablePagination-actions': { ml: 0.5 },
          }}
        />
      </TableContainer>
    </Paper>
  );
}

const monthlyColumns: TableColumn<IpcMonthlyPoint>[] = [
  { key: 'record_data', label: 'Дата', render: (row) => formatMonth(row.record_data) },
  { key: 'ipc', label: 'Общий ИПЦ, %', align: 'right', render: (row) => formatPercent(row.ipc) },
  { key: 'food_ipc', label: 'Продовольствие, %', align: 'right', render: (row) => formatPercent(row.food_ipc) },
  { key: 'non_food_ipc', label: 'Непрод. товары, %', align: 'right', render: (row) => formatPercent(row.non_food_ipc) },
  { key: 'services_ipc', label: 'Услуги, %', align: 'right', render: (row) => formatPercent(row.services_ipc) },
];

const weeklyColumns: TableColumn<IpcWeeklyPoint>[] = [
  { key: 'start_date', label: 'Начало периода', render: (row) => formatDate(row.start_date) },
  { key: 'end_date', label: 'Конец периода', render: (row) => formatDate(row.end_date) },
  { key: 'ipc_weekly', label: 'ИПЦ, %', align: 'right', render: (row) => formatPercent(row.ipc_weekly) },
  {
    key: 'ipc_weekly',
    label: 'Изменение',
    align: 'right',
    render: (row) => {
      const change = row.ipc_weekly == null ? null : row.ipc_weekly - 100;
      return (
        <Box component="span" sx={{ color: changeColor(change), fontWeight: 650 }}>
          {formatSignedNumber(change)}
        </Box>
      );
    },
  },
];

export const IpcPage: React.FC = () => {
  const [data, setData] = useState<IpcDashboardData | null>(null);
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
  const [dateTo, setDateTo] = useState<Dayjs | null>(null);
  const [chartTab, setChartTab] = useState(0);
  const [filterAnchor, setFilterAnchor] = useState<HTMLElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void fetchIpcDashboardData()
      .then((result) => { if (active) setData(result); })
      .catch((err: unknown) => {
        console.error(err);
        if (active) setError('Ошибка при загрузке данных по ИПЦ');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const visibleData = useMemo(() => {
    const from = dateFrom?.format('YYYY-MM-DD') ?? '';
    const till = dateTo?.format('YYYY-MM-DD') ?? '9999-12-31';
    const inRange = (value: string) => value >= from && value <= till;
    return {
      monthly: [...(data?.monthly ?? [])]
        .filter((row) => inRange(row.record_data))
        .sort((a, b) => a.record_data.localeCompare(b.record_data)),
      weekly: [...(data?.weekly ?? [])]
        .filter((row) => inRange(row.start_date))
        .sort((a, b) => a.start_date.localeCompare(b.start_date)),
    };
  }, [data, dateFrom, dateTo]);

  const monthlyChartRange = useMemo<[string, string] | undefined>(() => {
    if (!visibleData.monthly.length || dateFrom || dateTo) return undefined;
    const recent = visibleData.monthly.slice(-24);
    return [recent[0].record_data, recent[recent.length - 1].record_data];
  }, [visibleData.monthly, dateFrom, dateTo]);

  const monthlyChart = useMemo(() => [
    {
      x: visibleData.monthly.map((row) => row.record_data),
      y: visibleData.monthly.map((row) => row.ipc),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: 'Общий ИПЦ',
      line: { color: '#1677f2', width: 2.5 },
      marker: { color: '#1677f2', size: 5 },
      hovertemplate: '%{x|%d %B %Y}<br>Общий ИПЦ: <b>%{y:.2f}%</b><extra></extra>',
    },
    {
      x: visibleData.monthly.map((row) => row.record_data),
      y: visibleData.monthly.map((row) => row.food_ipc),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: 'Продовольственные товары',
      visible: 'legendonly' as const,
      line: { color: '#ed6c02', width: 2 },
      hovertemplate: '%{x|%d %B %Y}<br>Продовольственные товары: <b>%{y:.2f}%</b><extra></extra>',
    },
    {
      x: visibleData.monthly.map((row) => row.record_data),
      y: visibleData.monthly.map((row) => row.non_food_ipc),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: 'Непродовольственные товары',
      visible: 'legendonly' as const,
      line: { color: '#2e7d32', width: 2 },
      hovertemplate: '%{x|%d %B %Y}<br>Непродовольственные товары: <b>%{y:.2f}%</b><extra></extra>',
    },
    {
      x: visibleData.monthly.map((row) => row.record_data),
      y: visibleData.monthly.map((row) => row.services_ipc),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: 'Услуги',
      visible: 'legendonly' as const,
      line: { color: '#9c27b0', width: 2 },
      hovertemplate: '%{x|%d %B %Y}<br>Услуги: <b>%{y:.2f}%</b><extra></extra>',
    },
  ], [visibleData.monthly]);

  const weeklyChart = useMemo(() => {
    const recent = dateFrom || dateTo ? visibleData.weekly : visibleData.weekly.slice(-104);
    return [{
      x: recent.map((row) => row.start_date),
      // Bars grow from the 100% baseline so small deviations stay visible.
      y: recent.map((row) => row.ipc_weekly == null ? null : row.ipc_weekly - 100),
      base: 100,
      customdata: recent.map((row) => [row.end_date, row.ipc_weekly]),
      type: 'bar' as const,
      name: 'Недельный ИПЦ',
      marker: { color: '#1677f2' },
      hovertemplate: 'Период: %{x|%d %B %Y} — %{customdata[0]|%d %B %Y}<br>ИПЦ: <b>%{customdata[1]:.2f}%</b><br>Изменение: <b>%{y:+.2f}</b><extra></extra>',
    }];
  }, [visibleData.weekly, dateFrom, dateTo]);

  const kpi = data?.kpi;
  const indexCards = [
    { title: 'ИПЦ за неделю', value: formatPercent(kpi?.weekly.index), change: kpi?.weekly.change },
    { title: 'ИПЦ за месяц', value: formatPercent(kpi?.monthly.index), change: kpi?.monthly.change },
    { title: 'ИПЦ за 12 месяцев', value: formatPercent(kpi?.twelve_month.index), change: kpi?.twelve_month.change },
  ];
  const inflationCards = [
    { title: 'Инфляция за неделю', value: formatPercent(kpi?.weekly.inflation), change: kpi?.weekly.change },
    { title: 'Инфляция за месяц', value: formatPercent(kpi?.monthly.inflation), change: kpi?.monthly.change },
    { title: 'Накопленная инфляция с начала года', value: formatPercent(kpi?.year_to_date.inflation), change: kpi?.year_to_date.inflation },
  ];

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
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
          <Typography variant="h5" sx={{ color: '#102b50', fontWeight: 750, fontSize: { xs: '1.05rem', sm: '1.35rem' } }}>
            Индекс потребительских цен
          </Typography>
          <Stack direction="row" alignItems="center" spacing={0.25} sx={{ flexShrink: 0 }}>
            <Typography variant="caption" sx={{ color: '#607693', fontSize: { xs: '0.58rem', sm: '0.7rem' } }}>
              Обновлено: {formatDate(kpi?.last_observation_date)}
            </Typography>
            <Tooltip title="Фильтр периода">
              <IconButton
                aria-label="Фильтр периода"
                size="small"
                onClick={(event) => setFilterAnchor(event.currentTarget)}
                sx={{ color: dateFrom || dateTo ? '#1677f2' : '#6b83a3', p: 0.5 }}
              >
                <CalendarMonthOutlinedIcon sx={{ fontSize: 17 }} />
              </IconButton>
            </Tooltip>
          </Stack>
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
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Период графика и таблиц</Typography>
              <DatePicker label="С даты" value={dateFrom} onChange={setDateFrom} maxDate={dateTo ?? undefined} format="DD.MM.YYYY" slotProps={{ textField: { size: 'small' } }} />
              <DatePicker label="По дату" value={dateTo} onChange={setDateTo} minDate={dateFrom ?? undefined} format="DD.MM.YYYY" slotProps={{ textField: { size: 'small' } }} />
              <Button
                size="small"
                onClick={() => { setDateFrom(null); setDateTo(null); }}
                disabled={!dateFrom && !dateTo}
              >
                Сбросить период
              </Button>
            </Stack>
          </LocalizationProvider>
        </Popover>

        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}><CircularProgress /></Box>}
        {error && <Alert severity="error">{error}</Alert>}

        {!loading && !error && (
          <>
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))' },
              gap: { xs: 0.75, sm: 1.25 },
            }}>
              {[...indexCards.map((item) => ({ ...item, unit: '%' as const })), ...inflationCards.map((item) => ({ ...item, unit: 'п.п.' as const }))].map((item) => (
                <Card key={item.title} variant="outlined" sx={{
                  minWidth: 0,
                  minHeight: { xs: 72, sm: 88 },
                  borderColor: '#d9e7fb',
                  borderRadius: 2,
                  background: 'linear-gradient(145deg, #f8fbff 0%, #f2f7ff 100%)',
                  boxShadow: '0 1px 4px rgba(30, 81, 145, 0.05)',
                }}>
                  <CardContent sx={{ p: { xs: 1, sm: 1.5 }, '&:last-child': { pb: { xs: 1, sm: 1.5 } } }}>
                    <Typography variant="caption" sx={{ display: 'block', color: '#365477', lineHeight: 1.15, minHeight: '1.3em', fontSize: { xs: '0.64rem', sm: '0.76rem' } }}>
                      {item.title}
                    </Typography>
                    <Typography sx={{ mt: 0.5, color: '#122d51', fontWeight: 750, lineHeight: 1.05, fontSize: { xs: '1rem', sm: '1.3rem' } }}>
                      {item.value}
                    </Typography>
                    <Typography sx={{ mt: 0.5, fontWeight: 650, lineHeight: 1.1, fontSize: { xs: '0.64rem', sm: '0.76rem' }, color: changeColor(item.change) }}>
                      {formatChange(item.change, item.unit)}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>

            <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden', borderColor: '#dce8f8', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
              <Tabs
                value={chartTab}
                onChange={(_event, value: number) => setChartTab(value)}
                sx={{
                  minHeight: 40,
                  px: 1,
                  pt: 1,
                  pb: 0.5,
                  '& .MuiTabs-indicator': { display: 'none' },
                  '& .MuiTabs-flexContainer': { gap: 0.75 },
                  '& .MuiTab-root': {
                    minHeight: 32,
                    px: 2,
                    py: 0.5,
                    fontWeight: 650,
                    textTransform: 'none',
                    fontSize: '0.78rem',
                    borderRadius: 1.5,
                    color: '#365477',
                    bgcolor: '#eef4fd',
                    border: '1px solid #d9e7fb',
                  },
                  '& .MuiTab-root.Mui-selected': { color: '#fff', bgcolor: '#1677f2', borderColor: '#1677f2' },
                }}
              >
                <Tab label="Месячный ИПЦ" />
                <Tab label="Недельный ИПЦ" />
              </Tabs>
              <Box sx={{ px: { xs: 0.5, sm: 1.25 }, py: 0.5, minWidth: 0 }}>
                {chartTab === 0 ? (
                  visibleData.monthly.length ? (
                    <Plot
                      data={monthlyChart}
                      layout={{
                        autosize: true,
                        separators: ', ',
                        xaxis: { type: 'date', range: monthlyChartRange, tickformat: '%b %Y', dtick: 'M3', automargin: true, showgrid: true, gridcolor: '#e9f0fa', zeroline: false, ticks: 'outside', tickfont: { size: 12, color: '#56708f' } },
                        yaxis: { tickformat: '.0f', automargin: true, gridcolor: '#e9f0fa', zeroline: false, ticks: 'outside', tickfont: { size: 12, color: '#56708f' } },
                        showlegend: true,
                        legend: { orientation: 'h', x: 0, y: 1.12, font: { size: 12 } },
                        hovermode: 'x unified',
                        hoverlabel: { font: { size: 13 } },
                        margin: { l: 35, r: 8, t: 32, b: 30 },
                        plot_bgcolor: 'rgba(255,255,255,0)',
                        paper_bgcolor: 'rgba(255,255,255,0)',
                      }}
                      config={{ responsive: true, displayModeBar: true, scrollZoom: true, displaylogo: false, locale: 'ru', locales: russianPlotlyLocales }}
                      style={{ width: '100%', height: 'clamp(250px, 44vw, 440px)' }}
                    />
                  ) : <Typography color="text.secondary" sx={{ p: 2, textAlign: 'center', fontSize: '0.8rem' }}>Нет месячных данных за выбранный период</Typography>
                ) : (
                  visibleData.weekly.length ? (
                    <Plot
                      data={weeklyChart}
                      layout={{
                        autosize: true,
                        separators: ', ',
                        xaxis: { type: 'date', tickformat: '%b %Y', dtick: 'M3', automargin: true, showgrid: true, gridcolor: '#e9f0fa', zeroline: false, ticks: 'outside', tickfont: { size: 12, color: '#56708f' } },
                        yaxis: { tickformat: '.2f', automargin: true, gridcolor: '#e9f0fa', zeroline: false, ticks: 'outside', tickfont: { size: 12, color: '#56708f' } },
                        showlegend: false,
                        hovermode: 'x unified',
                        hoverlabel: { font: { size: 13 } },
                        margin: { l: 42, r: 8, t: 8, b: 30 },
                        plot_bgcolor: 'rgba(255,255,255,0)',
                        paper_bgcolor: 'rgba(255,255,255,0)',
                      }}
                      config={{ responsive: true, displayModeBar: true, scrollZoom: true, displaylogo: false, locale: 'ru', locales: russianPlotlyLocales }}
                      style={{ width: '100%', height: 'clamp(250px, 44vw, 440px)' }}
                    />
                  ) : <Typography color="text.secondary" sx={{ p: 2, textAlign: 'center', fontSize: '0.8rem' }}>Нет недельных данных за выбранный период</Typography>
                )}
              </Box>
            </Paper>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' }, gap: 1.25, minWidth: 0 }}>
              <HistoryTable
                title="Исторические месячные данные по ИПЦ"
                rows={[...visibleData.monthly].reverse()}
                columns={monthlyColumns}
                rowKey={(row) => row.record_data}
              />
              <HistoryTable
                title="Исторические недельные данные по ИПЦ"
                rows={[...visibleData.weekly].reverse()}
                columns={weeklyColumns}
                rowKey={(row) => row.start_date}
              />
            </Box>
            {!data?.monthly.length && !data?.weekly.length && <Alert severity="info">Данные ИПЦ отсутствуют</Alert>}
          </>
        )}
      </Stack>
    </Box>
  );
};

