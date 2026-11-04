import React, { useMemo } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Card,
  CardContent,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { ZerocuponRecord } from '../../api/zerocupon';
import {
  buildYieldCurveMap,
  interpolateZeroCurveYield,
} from '../../utils/zerocuponInterpolation';

const FLAT_BAND_PP = 0.25;
const DAY_MS = 24 * 60 * 60 * 1000;

const SPREADS = [
  { shortTerm: 2, label: '10Y–2Y', description: 'Классический показатель наклона кривой' },
  { shortTerm: 3, label: '10Y–3Y', description: 'Среднесрочный и долгосрочный сегменты' },
  { shortTerm: 5, label: '10Y–5Y', description: 'Наклон между пятилетним и десятилетним сроками' },
] as const;

const SUMMARY_CARD_SX = {
  minWidth: 0,
  borderColor: '#d9e7fb',
  borderRadius: 2,
  background: 'linear-gradient(145deg, rgba(255,255,255,0.92), rgba(242,247,255,0.84))',
  boxShadow: '0 2px 8px rgba(30, 81, 145, 0.06)',
};

type CurveStatus = 'normal' | 'flat' | 'inverted' | 'unavailable';

const getEpochDate = (value: string): number | null => {
  const match = value.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (match) return Date.UTC(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatDate = (value: string | null): string => {
  if (!value) return '—';
  const match = value.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (match) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('ru-RU');
};

const getYield = (record: ZerocuponRecord | null, term: number): number | null => {
  if (!record) return null;
  const curve = buildYieldCurveMap(record);
  return interpolateZeroCurveYield(curve, term);
};

const getSpread = (record: ZerocuponRecord | null, shortTerm: number): number | null => {
  const longYield = getYield(record, 10);
  const shortYield = getYield(record, shortTerm);
  if (longYield === null || shortYield === null) return null;
  return Math.round((longYield - shortYield) * 100) / 100;
};

const getReferenceRecord = (records: ZerocuponRecord[], latestDate: number, daysBack: number) => {
  const targetDate = latestDate - daysBack * DAY_MS;
  return records.reduce<ZerocuponRecord | null>((closest, record) => {
    const recordDate = getEpochDate(record.Дата);
    if (recordDate === null || recordDate > targetDate) return closest;
    if (!closest) return record;
    const closestDate = getEpochDate(closest.Дата);
    return closestDate === null || recordDate > closestDate ? record : closest;
  }, null);
};

const getStatus = (spread: number | null): CurveStatus => {
  if (spread === null) return 'unavailable';
  if (spread < -FLAT_BAND_PP) return 'inverted';
  if (spread <= FLAT_BAND_PP) return 'flat';
  return 'normal';
};

const STATUS_INFO: Record<CurveStatus, { label: string; color: 'success' | 'warning' | 'error' | 'default'; description: string }> = {
  normal: { label: 'Нормальный наклон', color: 'success', description: '10-летняя доходность выше доходности короткого срока' },
  flat: { label: 'Плоский участок', color: 'warning', description: 'Спред близок к нулю' },
  inverted: { label: 'Инверсия участка', color: 'error', description: 'Короткая доходность выше 10-летней' },
  unavailable: { label: 'Нет данных', color: 'default', description: 'Не удалось рассчитать спред' },
};

const formatSpread = (value: number | null): string => {
  if (value === null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} п.п.`;
};

const formatChange = (value: number | null): string => {
  if (value === null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} п.п.`;
};

interface YieldCurveSpreadsProps {
  records: ZerocuponRecord[];
}

/** Current curve slope, recent changes, and guidance for interpreting an inversion. */
export const YieldCurveSpreads: React.FC<YieldCurveSpreadsProps> = ({ records }) => {
  const metrics = useMemo(() => {
    const latestRecord = records.at(-1) ?? null;
    const latestDate = latestRecord ? getEpochDate(latestRecord.Дата) : null;
    const reference30 = latestDate === null ? null : getReferenceRecord(records, latestDate, 30);
    const reference90 = latestDate === null ? null : getReferenceRecord(records, latestDate, 90);

    return SPREADS.map((spread) => {
      const current = getSpread(latestRecord, spread.shortTerm);
      const old30 = getSpread(reference30, spread.shortTerm);
      const old90 = getSpread(reference90, spread.shortTerm);
      return {
        ...spread,
        current,
        change30: current === null || old30 === null ? null : Math.round((current - old30) * 100) / 100,
        change90: current === null || old90 === null ? null : Math.round((current - old90) * 100) / 100,
        referenceDate30: reference30?.Дата ?? null,
        referenceDate90: reference90?.Дата ?? null,
        status: getStatus(current),
      };
    });
  }, [records]);

  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
      <Box sx={{ px: { xs: 1.25, sm: 2 }, pt: 1.4, pb: 1.1 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between" spacing={0.5}>
          <Box>
            <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '0.95rem' }}>Наклон кривой и инверсия</Typography>
            <Typography sx={{ mt: 0.25, color: '#71839d', fontSize: '0.72rem' }}>
              Спреды доходностей 10-летних и более коротких ОФЗ
            </Typography>
          </Box>
          <Typography sx={{ color: '#71839d', fontSize: '0.68rem' }}>
            Плоский участок: от −{FLAT_BAND_PP.toLocaleString('ru-RU')} до +{FLAT_BAND_PP.toLocaleString('ru-RU')} п.п.
          </Typography>
        </Stack>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' }, gap: { xs: 0.75, sm: 1 }, px: { xs: 1.25, sm: 2 }, pb: 1.4 }}>
        {metrics.map((metric) => {
          const status = STATUS_INFO[metric.status];
          return (
            <Card key={metric.label} variant="outlined" sx={SUMMARY_CARD_SX}>
              <CardContent sx={{ p: { xs: 1.15, sm: 1.4 }, '&:last-child': { pb: { xs: 1.15, sm: 1.4 } } }}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={0.5}>
                  <Box>
                    <Typography sx={{ color: '#193c68', fontSize: '0.85rem', fontWeight: 750 }}>{metric.label}</Typography>
                    <Typography sx={{ mt: 0.2, color: '#71839d', fontSize: '0.65rem', lineHeight: 1.3 }}>{metric.description}</Typography>
                  </Box>
                  <Chip size="small" color={status.color} variant="outlined" label={status.label} sx={{ height: 22, fontSize: '0.62rem', flexShrink: 0 }} />
                </Stack>
                <Typography sx={{ mt: 1, color: '#122d51', fontSize: { xs: '1.25rem', sm: '1.35rem' }, lineHeight: 1.1, fontWeight: 750, fontVariantNumeric: 'tabular-nums' }}>
                  {formatSpread(metric.current)}
                </Typography>
                <Typography sx={{ mt: 0.2, color: '#71839d', fontSize: '0.64rem' }}>{status.description}</Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.5, mt: 1, pt: 0.8, borderTop: '1px solid #e5edf8' }}>
                  <Box>
                    <Typography sx={{ color: '#71839d', fontSize: '0.62rem' }}>Изменение за 30 дней</Typography>
                    <Typography sx={{ color: '#29476f', fontSize: '0.75rem', fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>{formatChange(metric.change30)}</Typography>
                    <Typography sx={{ color: '#8797ac', fontSize: '0.58rem' }}>{formatDate(metric.referenceDate30)}</Typography>
                  </Box>
                  <Box>
                    <Typography sx={{ color: '#71839d', fontSize: '0.62rem' }}>Изменение за 90 дней</Typography>
                    <Typography sx={{ color: '#29476f', fontSize: '0.75rem', fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>{formatChange(metric.change90)}</Typography>
                    <Typography sx={{ color: '#8797ac', fontSize: '0.58rem' }}>{formatDate(metric.referenceDate90)}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          );
        })}
      </Box>

      <Accordion disableGutters elevation={0} sx={{ borderTop: '1px solid #e5edf8', '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 40, px: { xs: 1.25, sm: 2 }, '& .MuiAccordionSummary-content': { my: 0.8 } }}>
          <Typography sx={{ color: '#365477', fontWeight: 650, fontSize: '0.75rem' }}>Как читать спреды и что означает инверсия</Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ px: { xs: 1.25, sm: 2 }, pt: 0, pb: 1.5 }}>
          <Stack spacing={1.25}>
            <Typography sx={{ color: '#48617f', fontSize: '0.74rem', lineHeight: 1.6 }}>
              При нормальном наклоне долгосрочные облигации обычно дают более высокую доходность: инвесторы требуют компенсацию за более долгий срок вложения. Инверсия возникает, когда доходность коротких бумаг выше долгосрочной, и может отражать ожидание снижения ставок в будущем.
            </Typography>

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))' }, gap: 0.75 }}>
              {[
                { title: 'Пример нормальной кривой', values: '3 года — 12% · 5 лет — 13% · 10 лет — 14%', color: '#2e7d32' },
                { title: 'Пример инверсии', values: '3 года — 16% · 5 лет — 14% · 10 лет — 12%', color: '#c62828' },
              ].map((example) => (
                <Paper key={example.title} variant="outlined" sx={{ p: 1, borderColor: '#e1eaf6', borderRadius: 1.5 }}>
                  <Typography sx={{ color: example.color, fontWeight: 700, fontSize: '0.7rem' }}>{example.title}</Typography>
                  <Typography sx={{ mt: 0.3, color: '#48617f', fontSize: '0.7rem' }}>{example.values}</Typography>
                  <Typography sx={{ mt: 0.2, color: '#8797ac', fontSize: '0.6rem' }}>Схема, не фактические доходности ОФЗ</Typography>
                </Paper>
              ))}
            </Box>

            <Typography sx={{ color: '#48617f', fontSize: '0.72rem', lineHeight: 1.6 }}>
              Формула: <b>S₁₀Y–ₙY = Y₁₀Y − YₙY</b>. Положительное значение означает, что доходность 10-летних ОФЗ выше; около нуля участок плоский; отрицательное значение указывает на инверсию. Например, 12% − 16% = −4 п.п., или −400 базисных пунктов. Для статуса «Плоский участок» здесь используется диапазон ±{FLAT_BAND_PP.toLocaleString('ru-RU')} п.п.; спреды интерполируются по ближайшим срокам кривой, если точного срока нет.
            </Typography>

            <Typography sx={{ color: '#48617f', fontSize: '0.72rem', lineHeight: 1.6 }}>
              10Y–2Y — классический показатель наклона; 10Y–3Y сравнивает среднесрочный и долгосрочный сегменты; 10Y–5Y показывает наклон на участке 5–10 лет. Изменение спреда считается как текущий спред минус значение на ближайшую доступную дату не позднее чем 30 или 90 дней назад. Снижение спреда означает уплощение участка, рост — его усиление.
            </Typography>

            <Typography sx={{ color: '#48617f', fontSize: '0.72rem', lineHeight: 1.6 }}>
              Для ОФЗ инверсия сама по себе не гарантирует скорого снижения ключевой ставки: на форму кривой также влияют инфляционные риски, премия за срок, ликвидность и объём предложения гособлигаций. Следите и за текущим наклоном, и за его изменением за 30 и 90 дней. Инверсия отдельного участка не означает, что инвертирована вся кривая.
            </Typography>
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
};
