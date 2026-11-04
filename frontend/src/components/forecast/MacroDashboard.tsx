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
  Legend,
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
type CurveSnapshot = MacroDashboardResponse['dashboard_charts']['yield_curve']['history'][number];

const colors = {
  blue: '#3977c3',
  teal: '#08a087',
  orange: '#ed9b38',
  purple: '#8065c4',
  red: '#d95c67',
  green: '#078d69',
  text: '#17345b',
  muted: '#6f819c',
  border: '#e1eaf5',
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
  if (indicator.key === 'ruonia') return `Спред ${sign}${formatNumber(indicator.change)} ${indicator.change_unit}`;
  const arrow = indicator.change > 0.005 ? '↑' : indicator.change < -0.005 ? '↓' : '•';
  return `${arrow} ${sign}${formatNumber(indicator.change)} ${indicator.change_unit}`;
};

const signalColor = (signal: MacroSignal): string => {
  if (!signal.is_available || signal.trend === 'unknown') return '#a0acbd';
  if (signal.trend === 'stable') return '#74849b';
  if (signal.trend === 'down') return colors.green;
  if (signal.trend === 'up') return colors.red;
  return colors.orange;
};

const signalIcon = (signal: MacroSignal) => {
  if (signal.trend === 'up') return <TrendingUpIcon />;
  if (signal.trend === 'down') return <TrendingDownIcon />;
  return <TrendingFlatIcon />;
};

const MetricCard: React.FC<{ indicator: MacroDashboardIndicator }> = ({ indicator }) => (
  <Card variant="outlined" sx={{ height: '100%', borderColor: colors.border, borderRadius: 2.25, boxShadow: '0 3px 12px rgba(39, 83, 139, 0.045)' }}>
    <CardContent sx={{ p: 1.7, '&:last-child': { pb: 1.7 }, display: 'flex', flexDirection: 'column', minHeight: 127 }}>
      <Typography sx={{ color: colors.muted, fontSize: '0.77rem', lineHeight: 1.35, minHeight: 32, fontWeight: 600 }}>
        {readableIndicatorLabels[indicator.key] ?? indicator.label}
      </Typography>
      <Typography sx={{ mt: 0.5, color: colors.text, fontSize: { xs: '1.55rem', lg: '1.8rem' }, fontWeight: 750, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {formatNumber(indicator.value)}%
      </Typography>
      <Typography sx={{ mt: 0.65, color: changeColor(indicator), fontSize: '0.72rem', fontWeight: 700, lineHeight: 1.25 }}>
        {changeText(indicator)} {indicator.key !== 'ruonia' && indicator.change != null && indicator.change_label ? `· ${indicator.change_label}` : ''}
      </Typography>
      <Typography sx={{ mt: 'auto', pt: 0.7, color: '#94a1b4', fontSize: '0.68rem' }}>
        {indicator.key === 'key_rate' ? 'Последнее решение' : 'Наблюдение'}: {formatDate(indicator.date)}
      </Typography>
    </CardContent>
  </Card>
);

const ChartPlot: React.FC<{
  data: ChartRecord[];
  lines: ChartLine[];
  height: number | string;
  flexible?: boolean;
  dateFormatter?: (date: string) => string;
  emptyText?: string;
}> = ({ data, lines, height, flexible = false, dateFormatter, emptyText = 'Нет доступных наблюдений' }) => {
  const hasValues = data.some((point) => lines.some((line) => (
    typeof point[line.key] === 'number' && Number.isFinite(point[line.key])
  )));
  const largeChart = typeof height === 'number' ? height > 300 : flexible;

  return (
    <Box sx={{ height: flexible ? 'auto' : height, flex: flexible ? '1 1 0' : '0 0 auto', minHeight: flexible ? 0 : undefined, minWidth: 0, px: 0.8, pt: 0.3, pb: 0.6 }}>
      {!hasValues ? (
        <Box sx={{ height: '100%', display: 'grid', placeItems: 'center' }}>
          <Typography color="text.secondary" fontSize="0.85rem">{emptyText}</Typography>
        </Box>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 15, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#edf2f8" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tickFormatter={dateFormatter ?? ((value: string) => formatDate(value, true))} tick={{ fill: '#8594a9', fontSize: largeChart ? 12 : 10 }} tickLine={false} axisLine={{ stroke: '#dce5f0' }} minTickGap={largeChart ? 30 : 22} />
            <YAxis domain={calculateYAxisDomain(data, lines)} tickCount={6} allowDataOverflow tick={{ fill: '#8594a9', fontSize: largeChart ? 12 : 10 }} tickLine={false} axisLine={false} tickFormatter={(value: number) => `${formatNumber(value, 1)}%`} width={58} />
            <ChartTooltip
              labelFormatter={(value) => dateFormatter ? String(value) : formatDate(String(value))}
              formatter={(value, name) => [value == null ? '—' : `${formatNumber(Number(value))}%`, name]}
              contentStyle={{ border: '1px solid #dfe8f3', borderRadius: 10, fontSize: 12, boxShadow: '0 6px 20px rgba(33,65,105,.12)' }}
            />
            <Legend wrapperStyle={{ fontSize: largeChart ? 13 : 11, paddingTop: 4 }} />
            {lines.map((line) => (
              <Line key={line.key} type="monotone" dataKey={line.key} name={line.label} stroke={line.color} strokeWidth={largeChart ? 3 : 2.3} dot={false} activeDot={{ r: largeChart ? 5 : 4 }} connectNulls={false} isAnimationActive={false} />
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
  data: ChartRecord[];
  historyData?: ChartRecord[];
  curveHistory?: CurveSnapshot[];
  defaultRange?: { from: string; to: string };
  lines: ChartLine[];
  spread?: number | null;
  height?: number;
  dateFormatter?: (date: string) => string;
  showLatestValues?: boolean;
  footer?: React.ReactNode;
}> = ({ title, subtitle, data, historyData, curveHistory, defaultRange, lines, spread, height = 218, dateFormatter, showLatestValues = true, footer }) => {
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
  const renderLatestValues = (values: ChartRecord[], valueLines: ChartLine[]) => (
    <Stack direction="row" flexWrap="wrap" gap={1.2} sx={{ px: 1.8, pb: 0.9 }}>
      {valueLines.map((line) => {
        const latest = [...values].reverse().find((point) => point[line.key] != null);
        const value = latest?.[line.key];
        return (
          <Typography key={line.key} sx={{ color: line.color, fontSize: '0.69rem', fontWeight: 700 }}>
            {line.label}: {value == null ? '—' : `${formatNumber(Number(value))}%`}
          </Typography>
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
      return <React.Fragment key={term}>{index > 0 ? ' · ' : ''}{label} {change == null ? '—' : `${change > 0 ? '+' : ''}${formatNumber(change)} п.п.`}</React.Fragment>;
    })
    : null;

  return (
    <>
      <Paper
        variant="outlined"
        role="button"
        tabIndex={0}
        aria-label={`Увеличить график «${title}» и выбрать диапазон`}
        onClick={openExpanded}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openExpanded();
          }
        }}
        sx={{
          minWidth: 0,
          borderRadius: 2.25,
          borderColor: colors.border,
          overflow: 'hidden',
          cursor: 'zoom-in',
          transition: 'transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease',
          '&:hover': { transform: 'translateY(-3px)', borderColor: '#b9d0ec', boxShadow: '0 9px 24px rgba(39, 83, 139, 0.13)' },
          '&:focus-visible': { outline: '2px solid #3977c3', outlineOffset: 2 },
          '@media (prefers-reduced-motion: reduce)': { transition: 'none', '&:hover': { transform: 'none' } },
        }}
      >
        <Box sx={{ px: 1.8, pt: 1.35, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ color: colors.text, fontWeight: 720, fontSize: '0.91rem' }}>{title}</Typography>
            {subtitle && <Typography sx={{ color: colors.muted, fontSize: '0.7rem', mt: 0.2 }}>{subtitle}</Typography>}
          </Box>
          <Stack direction="row" alignItems="center" gap={0.5}>
            {spread != null && (
              <Chip size="small" label={`Спред ${spread > 0 ? '+' : ''}${formatNumber(spread)} п.п.`} sx={{ bgcolor: '#eef5ff', color: colors.text, fontSize: '0.69rem', fontWeight: 700 }} />
            )}
            <Tooltip title="Увеличить и выбрать период">
              <IconButton size="small" aria-label={`Увеличить график «${title}»`} onClick={(event) => { event.stopPropagation(); openExpanded(); }} sx={{ color: colors.blue, ml: 0.25 }}>
                <OpenInFullIcon sx={{ fontSize: 17 }} />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>
        <ChartPlot data={data} lines={lines} height={height} dateFormatter={dateFormatter} />
        {showLatestValues && data.length > 0 && renderLatestValues(data, lines)}
        {footer && <Box sx={{ px: 1.8, pb: 1, color: colors.muted, fontSize: '0.7rem' }}>{footer}</Box>}
      </Paper>

      <Dialog
        open={expanded}
        onClose={() => setExpanded(false)}
        fullWidth
        maxWidth={false}
        PaperProps={{ sx: {
          width: { xs: 'calc(100% - 24px)', sm: 'calc(100% - 48px)' },
          height: { xs: 'calc(100% - 24px)', sm: 'calc(100% - 48px)' },
          maxWidth: 'none',
          maxHeight: 'none',
          m: { xs: 1.5, sm: 3 },
          borderRadius: { xs: 2, sm: 3 },
          border: `1px solid ${colors.border}`,
          overflow: 'hidden',
        } }}
      >
        <DialogTitle sx={{ px: { xs: 2, md: 3 }, py: 1.6, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2, color: colors.text, borderBottom: `1px solid ${colors.border}`, textTransform: 'none' }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography component="h2" sx={{ color: colors.text, fontSize: '1.1rem', fontWeight: 750, lineHeight: 1.3, textTransform: 'none', overflowWrap: 'anywhere' }}>{title}</Typography>
          </Box>
          <IconButton aria-label="Закрыть график" size="small" onClick={() => setExpanded(false)} sx={{ color: colors.muted, mt: -0.4, mr: -0.8 }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: { xs: 1.5, md: 2.5 }, bgcolor: '#f7f9fc', display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
          <Box sx={{
            display: 'grid',
            gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 190px))' },
            alignItems: 'start',
            gap: 1.2,
            mb: 1.3,
            minWidth: 0,
          }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography component="label" htmlFor={`${dateFieldId}-from`} sx={{ display: 'block', mb: 0.45, color: colors.muted, fontSize: '0.72rem', lineHeight: 1.3 }}>
                С даты
              </Typography>
              <TextField
                id={`${dateFieldId}-from`}
                type="date"
                size="small"
                fullWidth
                value={rangeFrom}
                onChange={(event) => setRangeFrom(event.target.value)}
                inputProps={{ min: minDate, max: rangeTo || maxDate }}
                sx={{ minWidth: 0, bgcolor: '#fff' }}
              />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography component="label" htmlFor={`${dateFieldId}-to`} sx={{ display: 'block', mb: 0.45, color: colors.muted, fontSize: '0.72rem', lineHeight: 1.3 }}>
                По дату
              </Typography>
              <TextField
                id={`${dateFieldId}-to`}
                type="date"
                size="small"
                fullWidth
                value={rangeTo}
                onChange={(event) => setRangeTo(event.target.value)}
                inputProps={{ min: rangeFrom || minDate, max: maxDate }}
                sx={{ minWidth: 0, bgcolor: '#fff' }}
              />
            </Box>
            <Typography sx={{ gridColumn: { xs: 'auto', sm: '1 / -1' }, minWidth: 0, color: colors.muted, fontSize: '0.75rem', overflowWrap: 'anywhere' }}>
              Доступно: {minDate ? formatDate(minDate) : '—'} — {maxDate ? formatDate(maxDate) : '—'}
            </Typography>
          </Box>
          <Paper variant="outlined" sx={{ borderColor: colors.border, borderRadius: 2.25, bgcolor: '#fff', overflow: 'hidden', display: 'flex', flexDirection: 'column', flex: '1 1 0', minHeight: 0 }}>
            <ChartPlot
              data={expandedData}
              lines={expandedLines}
              height="100%"
              flexible
              dateFormatter={curveHistory ? (value) => value : dateFormatter}
              emptyText={curveHistory ? 'Нет снимков кривой в выбранном диапазоне' : 'Нет наблюдений в выбранном диапазоне'}
            />
            {showLatestValues && expandedData.length > 0 && renderLatestValues(expandedData, expandedLines)}
            {curveHistory && selectedCurveChange && (
              <Typography sx={{ px: 1.8, pb: 1.2, color: colors.muted, fontSize: '0.8rem' }}>
                Изменение между выбранными снимками: {selectedCurveChange}
              </Typography>
            )}
          </Paper>
        </DialogContent>
        <DialogActions sx={{ px: { xs: 2, md: 3 }, py: 1.2, borderTop: `1px solid ${colors.border}` }}>
          <Button onClick={() => setExpanded(false)} variant="outlined" sx={{ borderColor: colors.border, color: colors.text, textTransform: 'none' }}>Закрыть</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

const SignalCard: React.FC<{ signal: MacroSignal }> = ({ signal }) => {
  const color = signalColor(signal);
  const populated = signal.indicators.filter((metric) => metric.signal != null);
  return (
    <Card variant="outlined" sx={{ height: '100%', borderColor: colors.border, borderRadius: 2.25 }}>
      <CardContent sx={{ p: 1.8, '&:last-child': { pb: 1.8 } }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
          <Typography sx={{ color: colors.text, fontSize: '0.88rem', fontWeight: 720 }}>{signal.name}</Typography>
          <Box sx={{ color, display: 'flex', '& svg': { fontSize: 19 } }}>{signalIcon(signal)}</Box>
        </Stack>
        <Typography sx={{ mt: 1, color, fontSize: '0.86rem', fontWeight: 750, lineHeight: 1.3 }}>{signal.status}</Typography>
        <Typography sx={{ mt: 0.65, minHeight: 38, color: '#687b95', fontSize: '0.73rem', lineHeight: 1.45 }}>{signal.explanation}</Typography>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mt: 1.1 }}>
          <Typography sx={{ color: colors.muted, fontSize: '0.7rem' }}>
            ↑ {signal.positive_count} · ↓ {signal.negative_count} · • {signal.neutral_count}
          </Typography>
          <Typography sx={{ color: colors.text, fontSize: '0.7rem', fontWeight: 700 }}>
            {Math.round(signal.data_coverage * 100)}% данных
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={Math.max(0, Math.min(100, signal.data_coverage * 100))}
          sx={{ mt: 0.7, height: 4, borderRadius: 3, bgcolor: '#eef2f7', '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 3 } }}
        />
        {populated.length > 0 && (
          <Tooltip title={populated.map((metric) => `${readableSignalMetricLabel(metric.key, metric.label)}: ${metric.signal! > 0 ? 'рост' : metric.signal! < 0 ? 'снижение' : 'без значимого изменения'}${metric.change == null ? '' : ` (${metric.change > 0 ? '+' : ''}${formatNumber(metric.change)} ${metric.unit})`}`).join(' · ')} arrow>
          <Typography sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1, color: '#617a9b', fontSize: '0.68rem', cursor: 'help' }}>
              Метрики, вошедшие в оценку <InfoOutlinedIcon sx={{ fontSize: 13 }} />
            </Typography>
          </Tooltip>
        )}
      </CardContent>
    </Card>
  );
};

const BalanceBlock: React.FC<{ groups: MacroBalanceGroup[]; index: number | null; status: string; interpretation: string; note: string; coverage: number }> = ({ groups, index, status, interpretation, note, coverage }) => {
  const groupColor: Record<MacroBalanceGroup['key'], string> = { cut: colors.green, hold: '#8696ab', hike: colors.red };
  return (
    <Paper variant="outlined" sx={{ p: { xs: 1.8, md: 2.2 }, borderRadius: 2.25, borderColor: colors.border }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between" gap={1}>
        <Box>
          <Typography sx={{ color: colors.text, fontSize: '0.98rem', fontWeight: 750 }}>Баланс сигналов</Typography>
          <Typography sx={{ color: colors.muted, fontSize: '0.72rem', mt: 0.25 }}>Распределение весов доступных направлений</Typography>
        </Box>
        <Stack direction="row" alignItems="center" gap={1}>
          <Typography sx={{ color: colors.muted, fontSize: '0.72rem' }}>Индекс направленности</Typography>
          <Chip label={index == null ? '—' : `${index > 0 ? '+' : ''}${formatNumber(index, 2)}`} sx={{ bgcolor: index == null ? '#f1f4f8' : index < -0.3 ? '#e9f7f1' : index > 0.3 ? '#fff0f1' : '#f1f4f8', color: index == null ? colors.muted : index < -0.3 ? colors.green : index > 0.3 ? colors.red : colors.text, fontWeight: 800, fontVariantNumeric: 'tabular-nums' }} />
        </Stack>
      </Stack>
      <Typography sx={{ mt: 1.5, mb: 1, color: colors.text, fontSize: '0.84rem', fontWeight: 650 }}>{status}</Typography>
      <Box role="img" aria-label="Горизонтальное распределение веса сигналов">
        <Box sx={{ display: 'flex', height: 16, overflow: 'hidden', borderRadius: 10, bgcolor: '#f0f3f7' }}>
          {groups.map((group) => (
            <Box key={group.key} sx={{ width: `${Math.max(0, group.share * 100)}%`, bgcolor: groupColor[group.key], transition: 'width 180ms ease' }} />
          ))}
        </Box>
      </Box>
      <Box sx={{ mt: 1.3, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 1.1 }}>
        {groups.map((group) => (
          <Box key={group.key} sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.9 }}>
            <Box sx={{ width: 9, height: 9, mt: 0.5, borderRadius: '50%', bgcolor: groupColor[group.key], flexShrink: 0 }} />
            <Box>
              <Typography sx={{ color: colors.text, fontSize: '0.75rem', fontWeight: 700 }}>{group.label}</Typography>
              <Typography sx={{ color: colors.muted, fontSize: '0.7rem', lineHeight: 1.5 }}>
                {group.count} сигналов · вес {formatNumber(group.weight * 100, 0)}% · доля {formatNumber(group.share * 100, 1)}%
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
      <Typography sx={{ mt: 1.4, color: '#526c8d', fontSize: '0.78rem', lineHeight: 1.5 }}>{interpretation}</Typography>
      <Typography sx={{ mt: 0.4, color: '#8a98aa', fontSize: '0.67rem' }}>
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
    return <Box sx={{ minHeight: 340, display: 'grid', placeItems: 'center' }}><CircularProgress size={30} /></Box>;
  }

  return (
    <Box sx={{ width: '100%', px: { xs: 1.2, md: 2.4 }, py: { xs: 1.3, md: 2 }, overflowY: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1} sx={{ mb: 1.6 }}>
        <Stack direction="row" alignItems="center" gap={1.2}>
          <Box sx={{ width: 39, height: 39, display: 'grid', placeItems: 'center', borderRadius: 2, bgcolor: '#eaf3ff', color: colors.blue }}><InsightsOutlinedIcon /></Box>
          <Box>
            <Typography component="h1" sx={{ color: colors.text, fontWeight: 800, fontSize: { xs: '1.1rem', md: '1.3rem' }, lineHeight: 1.2 }}>Макроэкономический обзор</Typography>
            <Typography sx={{ color: colors.muted, fontSize: '0.72rem', mt: 0.2 }}>Данные из аналитических разделов и детерминированная оценка сигналов</Typography>
          </Box>
        </Stack>
        <Tooltip title="Обновить данные">
          <span>
            <IconButton aria-label="Обновить макроэкономические данные" onClick={() => void load(true)} disabled={refreshing} size="small" sx={{ color: colors.blue, border: `1px solid ${colors.border}`, bgcolor: '#fff' }}>
              {refreshing ? <CircularProgress size={19} /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </span>
        </Tooltip>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 1.4 }} action={<IconButton size="small" onClick={() => void load(true)}><RefreshIcon fontSize="small" /></IconButton>}>{error}</Alert>}
      {data?.data_quality.warnings.map((warning) => <Alert key={warning} severity="warning" sx={{ mb: 1 }}>{warning}</Alert>)}

      {data && (
        <>
          <Box component="section" aria-label="Основные макроэкономические показатели" sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(3, minmax(0, 1fr))', lg: 'repeat(6, minmax(0, 1fr))' }, gap: 1.1 }}>
            {data.dashboard_indicators.map((indicator) => <MetricCard key={indicator.key} indicator={indicator} />)}
          </Box>

          <Box component="section" aria-label="Обзорные графики" sx={{ mt: 1.6, display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' }, gap: 1.2 }}>
            <ChartPanel title="Инфляция" subtitle="Изменение к предыдущему месяцу и за последние 12 месяцев" data={data.dashboard_charts.inflation.slice(-12)} historyData={data.dashboard_charts.inflation} lines={[{ key: 'mom', label: 'За месяц', color: colors.teal }, { key: 'yoy', label: 'За 12 месяцев', color: colors.orange }]} />
            <ChartPanel title="Инфляционные ожидания" subtitle={`Разрыв ожиданий и фактической инфляции: 1 год ${formatNumber(data.dashboard_charts.expectation_gaps.one_year.value)} п.п. · 5 лет ${formatNumber(data.dashboard_charts.expectation_gaps.five_year.value)} п.п.`} data={data.dashboard_charts.expectations.slice(-12)} historyData={data.dashboard_charts.expectations} lines={[{ key: 'actual_yoy', label: 'Фактическая инфляция за 12 месяцев', color: colors.blue }, { key: 'expected_1y', label: 'Ожидания, 1 год', color: colors.orange }, { key: 'expected_5y', label: 'Ожидания, 5 лет', color: colors.purple }]} />
            <ChartPanel title="Денежно-кредитные условия" subtitle="Ключевая ставка и RUONIA, последние 6 месяцев" data={trailingDays(data.dashboard_charts.monetary_conditions, 183)} historyData={data.dashboard_charts.monetary_conditions} lines={[{ key: 'key_rate', label: 'Ключевая ставка', color: colors.blue }, { key: 'ruonia', label: 'RUONIA', color: colors.teal }]} spread={data.dashboard_charts.monetary_conditions.length ? (() => { const latest = data.dashboard_charts.monetary_conditions.at(-1); return latest?.ruonia != null && latest.key_rate != null ? Number(latest.ruonia) - Number(latest.key_rate) : null; })() : null} />
            <ChartPanel title="Кривая доходности ОФЗ" subtitle={`Текущая кривая и ${formatDate(data.dashboard_charts.yield_curve.comparison_date)} · % годовых`} data={data.dashboard_charts.yield_curve.data.map((point) => ({ ...point, date: point.maturity }))} curveHistory={data.dashboard_charts.yield_curve.history} defaultRange={{ from: data.dashboard_charts.yield_curve.comparison_date ?? data.dashboard_charts.yield_curve.date ?? '', to: data.dashboard_charts.yield_curve.date ?? '' }} lines={[{ key: 'current', label: `На ${formatDate(data.dashboard_charts.yield_curve.date)}`, color: colors.blue }, { key: 'previous', label: '30 дней назад', color: colors.orange }]} height={218} dateFormatter={(value) => value} showLatestValues={false} footer={<>
              Изменение за 30 дней: {['term_2_0', 'term_5_0', 'term_10_0'].map((term, index) => {
                const point = data.dashboard_charts.yield_curve.data.find((item) => item.term === term);
                const label = ['2 года', '5 лет', '10 лет'][index];
                return <React.Fragment key={term}>{index > 0 ? ' · ' : ''}{label} {point?.change == null ? '—' : `${point.change > 0 ? '+' : ''}${formatNumber(point.change)} п.п.`}</React.Fragment>;
              })}
            </>} />
          </Box>

          <Box component="section" aria-label="Оценка макроэкономической ситуации" sx={{ mt: 1.8 }}>
            <Stack direction="row" alignItems="center" gap={0.8} sx={{ mb: 1 }}>
              <Typography component="h2" sx={{ color: colors.text, fontSize: '1rem', fontWeight: 780 }}>Автоматическая оценка</Typography>
              <Tooltip title="Правила и пороги расчёта вынесены в конфигурацию backend-модуля. Оценка не является прогнозом решения ЦБ.">
                <InfoOutlinedIcon sx={{ color: '#8b9ab0', fontSize: 16 }} />
              </Tooltip>
            </Stack>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', xl: 'repeat(4, minmax(0, 1fr))' }, gap: 1.1 }}>
              {data.macro_signals.map((signal) => <SignalCard key={signal.key} signal={signal} />)}
            </Box>
            <Box sx={{ mt: 1.2 }}>
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

          <Typography sx={{ mt: 1.2, mb: 0.5, color: '#97a4b5', fontSize: '0.66rem', textAlign: 'right' }}>
            Данные обновлены: {new Date(data.generated_at).toLocaleString('ru-RU')}
          </Typography>
        </>
      )}
    </Box>
  );
};
