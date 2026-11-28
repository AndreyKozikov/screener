import React, { useCallback, useEffect, useId, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fetchMacroDashboard } from '../../api/macroDashboard';
import type {
  MacroBalanceGroup,
  MacroDashboardIndicator,
  MacroDashboardResponse,
  MacroSignal,
} from '../../api/macroDashboard';

type ChartRecord = Record<string, string | number | null>;
type ChartLine = { key: string; label: string; color: string };
type ChartStat = { label: string; value: string };
type CurveSnapshot = MacroDashboardResponse['dashboard_charts']['yield_curve']['history'][number];

/**
 * Палитра раздела. Серый текст и цветные акценты подобраны с контрастом
 * не ниже 4,5:1 на белом, цветные линии графиков — не ниже 3:1.
 */
const colors = {
  blue: '#3977c3',
  teal: '#087f6c',
  orange: '#a86408',
  purple: '#8065c4',
  red: '#b23a48',
  green: '#0b6b52',
  text: '#17345b',
  muted: '#5b6b80',
  border: '#dbe5f1',
};

const readableIndicatorLabels: Record<string, string> = {
  inflation_yoy: 'Инфляция за 12 месяцев',
  inflation_mom: 'Инфляция за месяц',
};

const readableSignalMetricLabel = (key: string, label: string): string => (
  readableIndicatorLabels[key] ?? label
);

const formatNumber = (value: number | null | undefined, digits = 2): string => (
  value == null || !Number.isFinite(value)
    ? '—'
    : value.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
);

const formatDate = (value: string | null | undefined, month = false): string => {
  if (!value) return '—';
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', month
    ? { month: 'short', year: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' });
};

function trailingDays<T extends { date: string }>(records: T[], days: number): T[] {
  const latest = records.at(-1);
  if (!latest) return records;
  const cutoff = new Date(`${latest.date.slice(0, 10)}T00:00:00Z`);
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  const cutoffIso = cutoff.toISOString().slice(0, 10);
  return records.filter((record) => record.date.slice(0, 10) >= cutoffIso);
}

const calculateYAxisDomain = (
  data: Array<Record<string, string | number | null>>,
  lines: Array<{ key: string; label: string; color: string }>,
): [number, number] | ['auto', 'auto'] => {
  const values = data.flatMap((point) => lines
    .map((line) => point[line.key])
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value)));
  if (values.length === 0) return ['auto', 'auto'];

  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum;
  const padding = span > 0
    ? span * 0.12
    : Math.max(Math.abs(minimum) * 0.04, 0.1);
  return [minimum - padding, maximum + padding];
};

const changeColor = (indicator: MacroDashboardIndicator): string => {
  if (indicator.change == null || Math.abs(indicator.change) < 0.005 || indicator.tone === 'нейтральный') return colors.muted;
  return indicator.tone === 'дезинфляционный' ? colors.green : colors.red;
};

const changeText = (indicator: MacroDashboardIndicator): string => {
  if (indicator.change == null) return 'Нет сопоставимого значения';
  const sign = indicator.change > 0 ? '+' : '';
  if (indicator.key === 'ruonia') return `Спред ${sign}${formatNumber(indicator.change)}\u00A0${indicator.change_unit}`;
  const arrow = indicator.change > 0.005 ? '↑' : indicator.change < -0.005 ? '↓' : '•';
  return `${arrow} ${sign}${formatNumber(indicator.change)}\u00A0${indicator.change_unit}`;
};

const signalColor = (signal: MacroSignal): string => {
  if (!signal.is_available || signal.trend === 'unknown' || signal.trend === 'stable') return colors.muted;
  if (signal.trend === 'down') return colors.green;
  if (signal.trend === 'up') return colors.red;
  return colors.orange;
};

const signalIcon = (signal: MacroSignal) => {
  if (signal.trend === 'up') return <TrendingUpIcon />;
  if (signal.trend === 'down') return <TrendingDownIcon />;
  return <TrendingFlatIcon />;
};

const MetricCard: React.FC<{ indicator: MacroDashboardIndicator; lead?: boolean }> = ({ indicator, lead = false }) => {
  const unit = indicator.unit ?? '';
  const valueText = indicator.value == null || !Number.isFinite(indicator.value)
    ? '—'
    : `${formatNumber(indicator.value, 1)}${unit ? `\u00A0${unit}` : ''}`;
  const dateLabel = indicator.key === 'key_rate' ? 'Последнее решение' : 'Наблюдение';

  return (
    <Card
      variant="outlined"
      sx={{
        gridColumn: lead ? { xs: 'span 2', md: 'span 1' } : undefined,
        height: '100%',
        borderColor: lead ? '#c6dbf4' : colors.border,
        bgcolor: lead ? '#f4f8ff' : '#fff',
        borderRadius: 1.5,
        boxShadow: 'none',
      }}
    >
      <CardContent sx={{
        p: { xs: 1.5, sm: 2 },
        '&:last-child': { pb: { xs: 1.5, sm: 2 } },
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <Typography sx={{ color: colors.muted, fontSize: '0.8rem', lineHeight: 1.3, minHeight: '2.6em', fontWeight: 600 }}>
          {readableIndicatorLabels[indicator.key] ?? indicator.label}
        </Typography>
        <Typography sx={{
          mt: 1,
          color: colors.text,
          fontSize: lead ? '2.25rem' : '1.5rem',
          fontWeight: 700,
          lineHeight: 1.05,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}>
          {valueText}
        </Typography>
        <Typography sx={{ mt: 1, color: changeColor(indicator), fontSize: '0.8rem', fontWeight: 600, lineHeight: 1.35 }}>
          {changeText(indicator)} {indicator.key !== 'ruonia' && indicator.change != null && indicator.change_label ? `· ${indicator.change_label}` : ''}
        </Typography>
        <Typography sx={{ mt: 'auto', pt: 1.5, color: colors.muted, fontSize: '0.8rem', lineHeight: 1.3 }}>
          {dateLabel}: {formatDate(indicator.date)}
        </Typography>
      </CardContent>
    </Card>
  );
};

const ChartPlot: React.FC<{
  data: ChartRecord[];
  lines: ChartLine[];
  flexible?: boolean;
  dateFormatter?: (date: string) => string;
  emptyText?: string;
}> = ({ data, lines, flexible = false, dateFormatter, emptyText = 'Нет доступных наблюдений' }) => {
  const hasValues = data.some((point) => lines.some((line) => (
    typeof point[line.key] === 'number' && Number.isFinite(point[line.key])
  )));

  return (
    <Box sx={{
      height: flexible ? 'auto' : { xs: 200, sm: 220, md: 250, xl: 270 },
      flex: flexible ? '1 1 0' : '0 0 auto',
      minHeight: flexible ? '14rem' : undefined,
      minWidth: 0,
      px: 2,
      pt: 1,
    }}>
      {!hasValues ? (
        <Box sx={{ height: '100%', display: 'grid', placeItems: 'center' }}>
          <Typography sx={{ color: colors.muted, fontSize: '0.875rem' }}>{emptyText}</Typography>
        </Box>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
            <CartesianGrid stroke="#e8eef6" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={dateFormatter ?? ((value: string) => formatDate(value, true))}
              tick={{ fill: colors.muted, fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: '#cddaea' }}
              minTickGap={24}
            />
            <YAxis
              domain={calculateYAxisDomain(data, lines)}
              tickCount={5}
              allowDataOverflow
              tick={{ fill: colors.muted, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => `${formatNumber(value, 1)}%`}
              width={52}
            />
            <ChartTooltip
              labelFormatter={(value) => dateFormatter ? String(value) : formatDate(String(value))}
              formatter={(value, name) => [value == null ? '—' : `${formatNumber(Number(value))}%`, name]}
              contentStyle={{ border: `1px solid ${colors.border}`, borderRadius: 8, fontSize: 12, boxShadow: '0 6px 20px rgba(33, 65, 105, 0.12)' }}
            />
            {lines.map((line) => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.label}
                stroke={line.color}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
};

const ChartPanel: React.FC<{
  title: string;
  subtitle?: string;
  stats?: ChartStat[];
  data: ChartRecord[];
  historyData?: ChartRecord[];
  curveHistory?: CurveSnapshot[];
  defaultRange?: { from: string; to: string };
  lines: ChartLine[];
  dateFormatter?: (date: string) => string;
  showSeriesValues?: boolean;
}> = ({ title, subtitle, stats, data, historyData, curveHistory, defaultRange, lines, dateFormatter, showSeriesValues = true }) => {
  const [expanded, setExpanded] = useState(false);
  const [rangeFrom, setRangeFrom] = useState('');
  const [rangeTo, setRangeTo] = useState('');
  const dateFieldId = useId();
  const rangeData = historyData ?? data;
  const availableDates = curveHistory?.map((snapshot) => snapshot.date)
    ?? rangeData.map((point) => String(point.date ?? '')).filter(Boolean);
  const minDate = availableDates[0] ?? '';
  const maxDate = availableDates.at(-1) ?? '';
  const initialFrom = defaultRange?.from ?? String(data[0]?.date ?? minDate);
  const initialTo = defaultRange?.to ?? String(data.at(-1)?.date ?? maxDate);

  const openExpanded = () => {
    setRangeFrom(initialFrom);
    setRangeTo(initialTo);
    setExpanded(true);
  };

  const filteredHistory = useMemo(() => rangeData.filter((point) => {
    const pointDate = String(point.date ?? '');
    return pointDate && (!rangeFrom || pointDate >= rangeFrom) && (!rangeTo || pointDate <= rangeTo);
  }), [rangeData, rangeFrom, rangeTo]);

  const curveSelection = useMemo(() => {
    if (!curveHistory) return null;
    const selected = curveHistory.filter((snapshot) => (
      (!rangeFrom || snapshot.date >= rangeFrom) && (!rangeTo || snapshot.date <= rangeTo)
    ));
    const first = selected[0];
    const last = selected.at(-1);
    if (!first || !last) return { data: [] as ChartRecord[], lines: [] as ChartLine[], first: null, last: null };

    const curveLines: ChartLine[] = first.date === last.date
      ? [{ key: 'current', label: `На ${formatDate(last.date)}`, color: lines.find((line) => line.key === 'current')?.color ?? colors.blue }]
      : lines.map((line) => ({
        ...line,
        label: line.key === 'current' ? `На ${formatDate(last.date)}` : `На ${formatDate(first.date)}`,
      }));
    const plottedData = last.data.map((lastPoint) => ({
      date: lastPoint.maturity,
      current: lastPoint.value,
      previous: first.date === last.date
        ? null
        : first.data.find((point) => point.term === lastPoint.term)?.value ?? null,
    }));
    return { data: plottedData, lines: curveLines, first, last };
  }, [curveHistory, lines, rangeFrom, rangeTo]);

  const expandedData = curveSelection?.data ?? filteredHistory;
  const expandedLines = curveSelection?.lines.length ? curveSelection.lines : lines;

  // Подпись серии и последнее значение вместо цветного текста легенды.
  const renderSeriesValues = (values: ChartRecord[] | null, valueLines: ChartLine[]) => (
    <Stack direction="row" flexWrap="wrap" columnGap={2.5} rowGap={1} sx={{ px: 2, pt: 1, pb: 2 }}>
      {valueLines.map((line) => {
        const latest = values ? [...values].reverse().find((point) => point[line.key] != null) : undefined;
        const value = latest?.[line.key];
        return (
          <Box key={line.key} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Box sx={{ width: '0.875rem', height: '0.1875rem', borderRadius: '0.125rem', bgcolor: line.color, flexShrink: 0 }} />
            <Typography sx={{ color: colors.muted, fontSize: '0.8rem', lineHeight: 1.4 }}>{line.label}:</Typography>
            {values && (
              <Typography sx={{ color: colors.text, fontSize: '0.8rem', fontWeight: 600, lineHeight: 1.4, fontVariantNumeric: 'tabular-nums' }}>
                {value == null ? '—' : `${formatNumber(Number(value), 1)}\u00A0%`}
              </Typography>
            )}
          </Box>
        );
      })}
    </Stack>
  );

  const selectedCurveChange = curveSelection?.first && curveSelection.last && curveSelection.first.date !== curveSelection.last.date
    ? ['term_2_0', 'term_5_0', 'term_10_0'].map((term, index) => {
      const startValue = curveSelection.first!.data.find((point) => point.term === term)?.value;
      const endValue = curveSelection.last!.data.find((point) => point.term === term)?.value;
      const change = startValue == null || endValue == null ? null : endValue - startValue;
      const label = ['2 года', '5 лет', '10 лет'][index];
      return <React.Fragment key={term}>{index > 0 ? ' · ' : ''}{label}{' '}
        <Box component="span" sx={{ color: colors.text, fontWeight: 600 }}>{change == null ? '—' : `${change > 0 ? '+' : ''}${formatNumber(change)} п.п.`}</Box>
      </React.Fragment>;
    })
    : null;

  return (
    <>
      <Paper variant="outlined" sx={{ minWidth: 0, borderRadius: 1.5, borderColor: colors.border, overflow: 'hidden', boxShadow: 'none' }}>
        <Box sx={{ px: 2, pt: 2, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ color: colors.text, fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.3 }}>{title}</Typography>
            {subtitle && (
              <Typography sx={{ color: colors.muted, fontSize: '0.8rem', lineHeight: 1.4, mt: 0.5 }}>{subtitle}</Typography>
            )}
            {stats && stats.length > 0 && (
              <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', columnGap: 2, rowGap: 0.5 }}>
                {stats.map((stat) => (
                  <Typography key={stat.label} sx={{ color: colors.muted, fontSize: '0.8rem', lineHeight: 1.4 }}>
                    {stat.label}:{' '}
                    <Box component="span" sx={{ color: colors.text, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{stat.value}</Box>
                  </Typography>
                ))}
              </Box>
            )}
          </Box>
          <Tooltip title="Развернуть график">
            <IconButton
              aria-label={`Развернуть график «${title}»`}
              onClick={openExpanded}
              sx={{ flexShrink: 0, width: '3rem', height: '3rem', mt: -0.5, border: `1px solid ${colors.border}`, bgcolor: '#fff', color: colors.blue, '&:hover': { bgcolor: '#f2f7ff' } }}
            >
              <OpenInFullIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
        </Box>
        <ChartPlot data={data} lines={lines} dateFormatter={dateFormatter} />
        {renderSeriesValues(showSeriesValues ? data : null, lines)}
      </Paper>

      <Dialog
        open={expanded}
        onClose={() => setExpanded(false)}
        fullWidth
        maxWidth={false}
        slotProps={{ paper: { sx: {
          width: { xs: 'calc(100% - 16px)', sm: 'calc(100% - 48px)' },
          height: { xs: 'calc(100% - 16px)', sm: 'calc(100% - 48px)' },
          maxWidth: 'none',
          maxHeight: 'none',
          m: { xs: 1, sm: 3 },
          borderRadius: { xs: 2, sm: 3 },
          border: `1px solid ${colors.border}`,
          overflow: 'hidden',
        } } }}
      >
        <DialogTitle sx={{ px: { xs: 2, md: 3 }, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, color: colors.text, borderBottom: `1px solid ${colors.border}`, textTransform: 'none' }}>
          <Typography component="h2" sx={{ color: colors.text, fontSize: '1.2rem', fontWeight: 600, lineHeight: 1.3, textTransform: 'none', overflowWrap: 'anywhere' }}>{title}</Typography>
          <IconButton aria-label="Закрыть график" onClick={() => setExpanded(false)} sx={{ width: '3rem', height: '3rem', flexShrink: 0, color: colors.muted }}>
            <CloseIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: { xs: 2, md: 3 }, bgcolor: '#f7f9fc', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'auto' }}>
          <Box sx={{
            display: 'grid',
            gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 190px))' },
            alignItems: 'start',
            gap: 2,
            mb: 2,
            minWidth: 0,
          }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography component="label" htmlFor={`${dateFieldId}-from`} sx={{ display: 'block', mb: 0.5, color: colors.muted, fontSize: '0.8rem', lineHeight: 1.3 }}>
                С даты
              </Typography>
              <TextField
                id={`${dateFieldId}-from`}
                type="date"
                size="small"
                fullWidth
                value={rangeFrom}
                onChange={(event) => setRangeFrom(event.target.value)}
                slotProps={{ htmlInput: { min: minDate, max: rangeTo || maxDate } }}
                sx={{
                  minWidth: 0,
                  bgcolor: '#fff',
                  // 16px на телефоне: iOS Safari иначе зумит страницу при фокусе поля.
                  '& .MuiInputBase-input': { fontSize: { xs: '16px', sm: '0.9375rem' } },
                }}
              />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography component="label" htmlFor={`${dateFieldId}-to`} sx={{ display: 'block', mb: 0.5, color: colors.muted, fontSize: '0.8rem', lineHeight: 1.3 }}>
                По дату
              </Typography>
              <TextField
                id={`${dateFieldId}-to`}
                type="date"
                size="small"
                fullWidth
                value={rangeTo}
                onChange={(event) => setRangeTo(event.target.value)}
                slotProps={{ htmlInput: { min: rangeFrom || minDate, max: maxDate } }}
                sx={{
                  minWidth: 0,
                  bgcolor: '#fff',
                  '& .MuiInputBase-input': { fontSize: { xs: '16px', sm: '0.9375rem' } },
                }}
              />
            </Box>
            <Typography sx={{ gridColumn: { xs: 'auto', sm: '1 / -1' }, minWidth: 0, color: colors.muted, fontSize: '0.8rem', overflowWrap: 'anywhere' }}>
              Доступно: {minDate ? formatDate(minDate) : '—'} — {maxDate ? formatDate(maxDate) : '—'}
            </Typography>
          </Box>
          <Paper variant="outlined" sx={{ borderColor: colors.border, borderRadius: 1.5, bgcolor: '#fff', overflow: 'hidden', display: 'flex', flexDirection: 'column', flex: '1 1 0', minHeight: '16rem' }}>
            <ChartPlot
              data={expandedData}
              lines={expandedLines}
              flexible
              dateFormatter={curveHistory ? (value) => value : dateFormatter}
              emptyText={curveHistory ? 'Нет снимков кривой в выбранном диапазоне' : 'Нет наблюдений в выбранном диапазоне'}
            />
            {renderSeriesValues(showSeriesValues ? expandedData : null, expandedLines)}
            {curveHistory && selectedCurveChange && (
              <Typography sx={{ px: 2, pb: 2, color: colors.muted, fontSize: '0.8rem', lineHeight: 1.5 }}>
                Изменение между выбранными снимками: {selectedCurveChange}
              </Typography>
            )}
          </Paper>
        </DialogContent>
        <DialogActions sx={{ px: { xs: 2, md: 3 }, py: 1.5, borderTop: `1px solid ${colors.border}` }}>
          <Button
            onClick={() => setExpanded(false)}
            variant="outlined"
            sx={{ minHeight: '3rem', borderColor: colors.border, color: colors.text, textTransform: 'none' }}
          >
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

const SignalCard: React.FC<{ signal: MacroSignal }> = ({ signal }) => {
  const [helpOpen, setHelpOpen] = useState(false);
  const color = signalColor(signal);
  const populated = signal.indicators.filter((metric) => metric.signal != null);
  return (
    <Card variant="outlined" sx={{ height: '100%', borderColor: colors.border, borderRadius: 1.5, boxShadow: 'none' }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 }, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" gap={1}>
          <Typography component="h3" sx={{ color: colors.text, fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.35 }}>{signal.name}</Typography>
          <Box aria-hidden sx={{ color, display: 'flex', flexShrink: 0, mt: 0.25, '& svg': { fontSize: 20 } }}>{signalIcon(signal)}</Box>
        </Stack>
        <Typography sx={{ mt: 1.5, color, fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.35 }}>{signal.status}</Typography>
        <Typography sx={{ mt: 1, color: colors.muted, fontSize: '0.875rem', lineHeight: 1.5, flexGrow: 1 }}>{signal.explanation}</Typography>
        <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1} sx={{ mt: 2 }}>
          <Typography sx={{ color: colors.muted, fontSize: '0.8rem' }}>
            ↑ {signal.positive_count} · ↓ {signal.negative_count} · • {signal.neutral_count}
          </Typography>
          <Typography sx={{ color: colors.text, fontSize: '0.8rem', fontWeight: 600 }}>
            {Math.round(signal.data_coverage * 100)}% данных
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={Math.max(0, Math.min(100, signal.data_coverage * 100))}
          sx={{ mt: 1, height: '0.375rem', borderRadius: '0.1875rem', bgcolor: '#e8eef6', '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: '0.1875rem' } }}
        />
        {populated.length > 0 && (
          <Tooltip
            title={populated.map((metric) => `${readableSignalMetricLabel(metric.key, metric.label)}: ${metric.signal! > 0 ? 'рост' : metric.signal! < 0 ? 'снижение' : 'без значимого изменения'}${metric.change == null ? '' : ` (${metric.change > 0 ? '+' : ''}${formatNumber(metric.change)} ${metric.unit})`}`).join(' · ')}
            open={helpOpen}
            onOpen={() => setHelpOpen(true)}
            onClose={() => setHelpOpen(false)}
            arrow
          >
            <Button
              size="small"
              onClick={() => setHelpOpen((value) => !value)}
              startIcon={<InfoOutlinedIcon sx={{ fontSize: 16 }} />}
              sx={{ mt: 1, px: 0, minHeight: '3rem', justifyContent: 'flex-start', textTransform: 'none', fontSize: '0.8rem', fontWeight: 500, color: colors.muted, '&:hover': { bgcolor: 'transparent', color: colors.text } }}
            >
              Метрики, вошедшие в оценку
            </Button>
          </Tooltip>
        )}
      </CardContent>
    </Card>
  );
};

const BalanceBlock: React.FC<{ groups: MacroBalanceGroup[]; index: number | null; status: string; interpretation: string; note: string; coverage: number }> = ({ groups, index, status, interpretation, note, coverage }) => {
  const groupColor: Record<MacroBalanceGroup['key'], string> = { cut: colors.green, hold: colors.muted, hike: colors.red };
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 }, borderRadius: 1.5, borderColor: colors.border, boxShadow: 'none' }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between" gap={1.5}>
        <Box>
          <Typography component="h3" sx={{ color: colors.text, fontSize: '0.9375rem', fontWeight: 600 }}>Баланс сигналов</Typography>
          <Typography sx={{ color: colors.muted, fontSize: '0.8rem', mt: 0.5 }}>Распределение весов доступных направлений</Typography>
        </Box>
        <Stack direction="row" alignItems="center" gap={1.5}>
          <Typography sx={{ color: colors.muted, fontSize: '0.8rem' }}>Индекс направленности</Typography>
          <Chip
            label={index == null ? '—' : `${index > 0 ? '+' : ''}${formatNumber(index, 2)}`}
            sx={{
              height: '2rem',
              bgcolor: index == null ? '#eef2f7' : index < -0.3 ? '#e9f7f1' : index > 0.3 ? '#fdeff1' : '#eef2f7',
              color: index == null ? colors.muted : index < -0.3 ? colors.green : index > 0.3 ? colors.red : colors.text,
              fontSize: '0.875rem',
              fontWeight: 600,
              fontVariantNumeric: 'tabular-nums',
            }}
          />
        </Stack>
      </Stack>
      <Typography sx={{ mt: 2, color: colors.text, fontSize: '0.9375rem', fontWeight: 600 }}>{status}</Typography>
      <Box role="img" aria-label="Горизонтальное распределение веса сигналов" sx={{ mt: 1.5 }}>
        <Box sx={{ display: 'flex', height: '0.5rem', overflow: 'hidden', borderRadius: '0.25rem', bgcolor: '#eef2f7' }}>
          {groups.map((group) => (
            <Box key={group.key} sx={{ width: `${Math.max(0, group.share * 100)}%`, bgcolor: groupColor[group.key] }} />
          ))}
        </Box>
      </Box>
      <Box sx={{ mt: 2, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 1.5 }}>
        {groups.map((group) => (
          <Box key={group.key} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <Box sx={{ width: '0.625rem', height: '0.625rem', mt: 0.5, borderRadius: '50%', bgcolor: groupColor[group.key], flexShrink: 0 }} />
            <Box>
              <Typography sx={{ color: colors.text, fontSize: '0.875rem', fontWeight: 600 }}>{group.label}</Typography>
              <Typography sx={{ color: colors.muted, fontSize: '0.8rem', lineHeight: 1.5 }}>
                {group.count} сигналов · вес {formatNumber(group.weight * 100, 0)}% · доля {formatNumber(group.share * 100, 1)}%
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
      <Typography sx={{ mt: 2.5, color: colors.text, fontSize: '0.9375rem', lineHeight: 1.55, maxWidth: '72ch' }}>{interpretation}</Typography>
      <Typography sx={{ mt: 1, color: colors.muted, fontSize: '0.8rem', lineHeight: 1.4 }}>
        Покрытие весов: {formatNumber(coverage * 100, 0)}%. {note}
      </Typography>
    </Paper>
  );
};

export const MacroDashboard: React.FC = () => {
  const [data, setData] = useState<MacroDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assessmentHelpOpen, setAssessmentHelpOpen] = useState(false);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      setData(await fetchMacroDashboard());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить макроэкономический дашборд');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading && !data) {
    return <Box sx={{ minHeight: '22rem', display: 'grid', placeItems: 'center' }}><CircularProgress size="2rem" /></Box>;
  }

  const indicators = data?.dashboard_indicators ?? [];
  const leadIndicator = indicators.find((indicator) => indicator.key === 'key_rate') ?? indicators[0] ?? null;
  const otherIndicators = leadIndicator ? indicators.filter((indicator) => indicator !== leadIndicator) : indicators;

  return (
    <Box sx={{ width: '100%', maxWidth: '80rem', mx: 'auto', px: { xs: 2, md: 4 }, py: { xs: 2, md: 3 } }}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" gap={2} sx={{ mb: { xs: 2, sm: 3 } }}>
        <Stack direction="row" alignItems="center" gap={{ xs: 1.5, sm: 2 }} sx={{ minWidth: 0 }}>
          <Box aria-hidden sx={{ width: { xs: '2.5rem', sm: '2.75rem' }, height: { xs: '2.5rem', sm: '2.75rem' }, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: 1.5, bgcolor: '#eaf3ff', color: colors.blue }}>
            <InsightsOutlinedIcon sx={{ fontSize: { xs: 20, sm: 22 } }} />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography component="h1" sx={{ color: colors.text, fontWeight: 700, fontSize: { xs: '1.4rem', md: '1.6rem' }, lineHeight: 1.2 }}>
              Макроэкономический обзор
            </Typography>
            <Typography sx={{ display: { xs: 'none', sm: 'block' }, color: colors.muted, fontSize: '0.875rem', lineHeight: 1.4, mt: 0.5 }}>
              Данные из аналитических разделов и детерминированная оценка сигналов
            </Typography>
          </Box>
        </Stack>
        <Tooltip title="Обновить данные">
          <span>
            <IconButton
              aria-label="Обновить макроэкономические данные"
              onClick={() => void load(true)}
              disabled={refreshing}
              sx={{ width: '3rem', height: '3rem', border: `1px solid ${colors.border}`, bgcolor: '#fff', color: colors.blue, '&:hover': { bgcolor: '#f2f7ff' } }}
            >
              {refreshing ? <CircularProgress size={20} /> : <RefreshIcon sx={{ fontSize: 20 }} />}
            </IconButton>
          </span>
        </Tooltip>
      </Stack>

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={<IconButton aria-label="Повторить загрузку" onClick={() => void load(true)} sx={{ width: '3rem', height: '3rem' }}><RefreshIcon /></IconButton>}
        >
          {error}
        </Alert>
      )}
      {data?.data_quality.warnings.map((warning) => <Alert key={warning} severity="warning" sx={{ mb: 1.5 }}>{warning}</Alert>)}

      {data && (
        <>
          <Box
            component="section"
            aria-label="Основные макроэкономические показатели"
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'repeat(2, minmax(0, 1fr))',
                md: 'repeat(3, minmax(0, 1fr))',
                lg: 'repeat(6, minmax(0, 1fr))',
              },
              gap: 1.5,
            }}
          >
            {leadIndicator && <MetricCard indicator={leadIndicator} lead />}
            {otherIndicators.map((indicator) => <MetricCard key={indicator.key} indicator={indicator} />)}
          </Box>

          <Box
            component="section"
            aria-label="Обзорные графики"
            sx={{
              mt: { xs: 3, md: 4 },
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
              gap: 2,
              alignItems: 'stretch',
            }}
          >
            <ChartPanel
              title="Инфляция"
              subtitle="Изменение к предыдущему месяцу и за последние 12 месяцев"
              data={data.dashboard_charts.inflation.slice(-12)}
              historyData={data.dashboard_charts.inflation}
              lines={[
                { key: 'mom', label: 'За месяц', color: colors.teal },
                { key: 'yoy', label: 'За 12 месяцев', color: colors.orange },
              ]}
            />
            <ChartPanel
              title="Инфляционные ожидания"
              subtitle="Ожидаемая и фактическая инфляция"
              stats={[
                { label: 'Разрыв, 1 год', value: `${formatNumber(data.dashboard_charts.expectation_gaps.one_year.value)} п.п.` },
                { label: '5 лет', value: `${formatNumber(data.dashboard_charts.expectation_gaps.five_year.value)} п.п.` },
              ]}
              data={data.dashboard_charts.expectations.slice(-12)}
              historyData={data.dashboard_charts.expectations}
              lines={[
                { key: 'actual_yoy', label: 'Факт, 12 мес.', color: colors.blue },
                { key: 'expected_1y', label: 'Ожидания, 1 год', color: colors.orange },
                { key: 'expected_5y', label: 'Ожидания, 5 лет', color: colors.purple },
              ]}
            />
            <ChartPanel
              title="Денежно-кредитные условия"
              subtitle="Ключевая ставка и RUONIA, последние 6 месяцев"
              stats={data.dashboard_charts.monetary_conditions.length ? (() => {
                const latest = data.dashboard_charts.monetary_conditions.at(-1);
                const spread = latest?.ruonia != null && latest.key_rate != null
                  ? Number(latest.ruonia) - Number(latest.key_rate)
                  : null;
                return spread == null
                  ? undefined
                  : [{ label: 'Спред ключевая — RUONIA', value: `${spread > 0 ? '+' : ''}${formatNumber(spread)} п.п.` }];
              })() : undefined}
              data={trailingDays(data.dashboard_charts.monetary_conditions, 183)}
              historyData={data.dashboard_charts.monetary_conditions}
              lines={[
                { key: 'key_rate', label: 'Ключевая ставка', color: colors.blue },
                { key: 'ruonia', label: 'RUONIA', color: colors.teal },
              ]}
            />
            <ChartPanel
              title="Кривая доходности ОФЗ"
              subtitle={`Текущая кривая и ${formatDate(data.dashboard_charts.yield_curve.comparison_date)} · % годовых`}
              stats={['term_2_0', 'term_5_0', 'term_10_0'].map((term, index) => {
                const point = data.dashboard_charts.yield_curve.data.find((item) => item.term === term);
                const label = ['2 года', '5 лет', '10 лет'][index];
                return {
                  label,
                  value: point?.change == null ? '—' : `${point.change > 0 ? '+' : ''}${formatNumber(point.change)} п.п.`,
                };
              })}
              data={data.dashboard_charts.yield_curve.data.map((point) => ({ ...point, date: point.maturity }))}
              curveHistory={data.dashboard_charts.yield_curve.history}
              defaultRange={{ from: data.dashboard_charts.yield_curve.comparison_date ?? data.dashboard_charts.yield_curve.date ?? '', to: data.dashboard_charts.yield_curve.date ?? '' }}
              lines={[
                { key: 'current', label: `На ${formatDate(data.dashboard_charts.yield_curve.date)}`, color: colors.blue },
                { key: 'previous', label: '30 дней назад', color: colors.orange },
              ]}
              dateFormatter={(value) => value}
              showSeriesValues={false}
            />
          </Box>

          <Box component="section" aria-label="Оценка макроэкономической ситуации" sx={{ mt: { xs: 3, md: 4 } }}>
            <Stack component="header" direction="row" alignItems="center" flexWrap="wrap" columnGap={1} rowGap={0.5} sx={{ mb: 1.5 }}>
              <Typography component="h2" sx={{ color: colors.text, fontSize: '1.2rem', fontWeight: 600, lineHeight: 1.3 }}>
                Автоматическая оценка
              </Typography>
              <Tooltip
                title="Правила и пороги расчёта вынесены в конфигурацию backend-модуля. Оценка не является прогнозом решения ЦБ."
                open={assessmentHelpOpen}
                onOpen={() => setAssessmentHelpOpen(true)}
                onClose={() => setAssessmentHelpOpen(false)}
                arrow
              >
                <Button
                  size="small"
                  onClick={() => setAssessmentHelpOpen((value) => !value)}
                  startIcon={<InfoOutlinedIcon sx={{ fontSize: 16 }} />}
                  sx={{ minHeight: '3rem', px: 1, textTransform: 'none', fontSize: '0.8rem', fontWeight: 500, color: colors.muted, '&:hover': { bgcolor: 'transparent', color: colors.text } }}
                >
                  Как считается
                </Button>
              </Tooltip>
            </Stack>
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(4, minmax(0, 1fr))' },
              gap: 1.5,
            }}>
              {data.macro_signals.map((signal) => <SignalCard key={signal.key} signal={signal} />)}
            </Box>
            <Box sx={{ mt: 2 }}>
              <BalanceBlock
                groups={data.macro_assessment.balance}
                index={data.macro_assessment.index}
                status={data.macro_assessment.status}
                interpretation={data.macro_assessment.interpretation}
                note={data.macro_assessment.note}
                coverage={data.macro_assessment.coverage}
              />
            </Box>
          </Box>

          <Typography sx={{ mt: 2, color: colors.muted, fontSize: '0.8rem', textAlign: 'right' }}>
            Данные обновлены: {new Date(data.generated_at).toLocaleString('ru-RU')}
          </Typography>
        </>
      )}
    </Box>
  );
};
