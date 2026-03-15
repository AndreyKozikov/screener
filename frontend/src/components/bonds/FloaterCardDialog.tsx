import React, { useCallback, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  Chip,
  Tooltip,
  Divider,
  Fade,
  Backdrop,
  Skeleton,
  Stack,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import type { BondFloatParamsDTO } from '../../types/bondFloatParams';

export interface FloaterCardDialogProps {
  open: boolean;
  onClose: () => void;
  data: BondFloatParamsDTO | null;
}

const indicatorNames: Record<string, string> = {
  KEY_RATE: 'Ключевая ставка ЦБ РФ',
  RUONIA: 'Ставка RUONIA (межбанковские кредиты)',
  RUSFAR: 'Ставка RUSFAR (рынок репо)',
  CPI: 'Индекс потребительских цен (инфляция)',
  GCURVE: 'Доходность гособлигаций (ОФЗ)',
  CUSTOM: 'Индивидуальный индикатор',
};

const indicatorHints: Record<string, string> = {
  KEY_RATE: 'Основной инструмент денежно-кредитной политики Банка России.',
  RUONIA: 'Средневзвешенная ставка, по которой крупнейшие банки кредитуют друг друга на один день.',
  RUSFAR: 'Справедливая стоимость денег на российском рынке, рассчитываемая Московской биржей.',
  CPI: 'Показатель уровня инфляции в стране.',
};

const ACCRUAL_TYPE_LABELS: Record<string, string> = {
  DAILY_ACCRUAL: 'Ежедневное начисление',
  FIXED_PERIOD: 'Фиксированная ставка на период',
};

const CALCULATION_TYPE_LABELS: Record<string, string> = {
  DAILY: 'Ежедневный пересчёт',
  FIXED: 'Фиксированная на период',
};

const KEY_RATE_METHOD_LABELS: Record<string, string> = {
  SPOT: 'Значение на дату (SPOT)',
  MA: 'Скользящее среднее (MA)',
};

const LOOKBACK_LABELS: Record<string, string> = {
  CALENDAR: 'Календарные дни',
  BUSINESS: 'Рабочие дни',
};

const FALLBACK_LABELS: Record<string, string> = {
  PRECEDING: 'Предыдущий рабочий день',
  FOLLOWING: 'Следующий рабочий день',
};

const observationTypeNames: Record<string, string> = {
  POINT: 'Значение на дату',
  AVERAGE: 'Среднее за период',
  INTERVAL: 'За макро-период',
};

const observationTypeHints: Record<string, string> = {
  POINT: 'Ставка купона привязана к значению индикатора в один конкретный день.',
  AVERAGE: 'Для расчета берется среднее значение индикатора за несколько дней. Это защищает от случайных резких всплесков ставки.',
  INTERVAL: 'Ставка берется как готовый показатель за длительный период (например, значение инфляции за квартал).',
};

const DAY_COUNT_REAL_CALENDAR_HINT =
  'Доход начисляется за каждый фактический день владения. В длинных месяцах (31 день) вы получите чуть больше, в коротких (февраль) — чуть меньше. Это самый точный расчет.';
const DAY_COUNT_30_360_HINT =
  'Для простоты расчетов считается, что в каждом месяце ровно 30 дней. Это позволяет получать одинаковую сумму дохода каждый месяц, независимо от календаря.';

function formatDaysToMaturity(days: number): string {
  const years = Math.floor(days / 365);
  const remainingDays = days % 365;
  const months = Math.floor(remainingDays / 30);
  const parts: string[] = [];
  if (years > 0) parts.push(`${years} ${pluralYears(years)}`);
  if (months > 0) parts.push(`${months} ${pluralMonths(months)}`);
  if (parts.length === 0) parts.push(`${days} дн.`);
  return parts.join(' ');
}

function pluralYears(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'год';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'года';
  return 'лет';
}

function pluralMonths(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'месяц';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'месяца';
  return 'месяцев';
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return iso;
  }
}

interface FieldRowProps {
  label: string;
  value: React.ReactNode;
  tooltip?: string;
  /** Длинная подсказка к заголовку; при наличии рядом с заголовком выводится иконка с этой подсказкой */
  labelTooltip?: string;
}

const FieldRow: React.FC<FieldRowProps> = ({ label, value, tooltip, labelTooltip }) => {
  const labelNode = (
    <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
      {label}
    </Typography>
  );

  const labelBlock = (
    <Box sx={{ minWidth: 200, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {tooltip ? (
        <Tooltip title={tooltip} arrow placement="top-start">
          <Box sx={{ cursor: 'help', borderBottom: '1px dotted', borderColor: 'text.disabled' }}>
            {labelNode}
          </Box>
        </Tooltip>
      ) : (
        labelNode
      )}
      {labelTooltip != null && labelTooltip !== '' && (
        <Tooltip title={labelTooltip} arrow placement="top-start">
          <HelpOutlineIcon fontSize="small" sx={{ color: 'text.secondary', cursor: 'help' }} />
        </Tooltip>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', py: 0.5, gap: 2 }}>
      {labelBlock}
      <Typography variant="body2" sx={{ fontWeight: 500 }}>
        {value}
      </Typography>
    </Box>
  );
};

interface SectionProps {
  title: string;
  children: React.ReactNode;
}

const Section: React.FC<SectionProps> = ({ title, children }) => (
  <Box sx={{ mb: 3 }}>
    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1, color: 'primary.main' }}>
      {title}
    </Typography>
    <Divider sx={{ mb: 1.5 }} />
    {children}
  </Box>
);

const LoadingSkeleton: React.FC = () => (
  <Box sx={{ p: 2 }}>
    <Skeleton variant="text" width="60%" height={32} />
    <Skeleton variant="text" width="40%" height={24} sx={{ mt: 1 }} />
    <Divider sx={{ my: 2 }} />
    {[...Array(5)].map((_, i) => (
      <Skeleton key={i} variant="text" width={`${70 + Math.random() * 30}%`} height={24} sx={{ my: 0.5 }} />
    ))}
    <Divider sx={{ my: 2 }} />
    {[...Array(4)].map((_, i) => (
      <Skeleton key={i} variant="text" width={`${60 + Math.random() * 40}%`} height={24} sx={{ my: 0.5 }} />
    ))}
  </Box>
);

export const FloaterCardDialog: React.FC<FloaterCardDialogProps> = ({ open, onClose, data }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyFormula = useCallback(() => {
    if (!data?.formula_raw) return;
    navigator.clipboard.writeText(data.formula_raw).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [data?.formula_raw]);

  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      TransitionComponent={Fade}
      TransitionProps={{ timeout: 300 }}
      BackdropComponent={Backdrop}
      BackdropProps={{ timeout: 300, onClick: handleBackdropClick }}
      PaperProps={{
        sx: { borderRadius: 2, maxHeight: '90vh', m: { xs: 2, sm: 3 } },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box>
          <Typography variant="h6" component="span" fontWeight={700}>
            {data ? `${data.name_short ?? data.secid}` : 'Параметры флоатера'}
          </Typography>
          {data && (
            <Typography variant="body2" color="text.secondary">
              {data.secid}
            </Typography>
          )}
        </Box>
        <IconButton onClick={onClose} size="small" aria-label="Закрыть" sx={{ ml: 2 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent
        sx={{
          pt: 3,
          pb: 2,
          '&::-webkit-scrollbar': { width: '8px' },
          '&::-webkit-scrollbar-track': { bgcolor: 'action.hover' },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'action.disabled',
            borderRadius: '4px',
            '&:hover': { bgcolor: 'text.secondary' },
          },
        }}
      >
        {!data ? (
          <LoadingSkeleton />
        ) : (
          <Box>
            {/* Основные параметры */}
            <Section title="Основные параметры">
              {data.nominal != null && (
                <FieldRow label="Номинал" value={`${data.nominal.toLocaleString('ru-RU')} ₽`} />
              )}
              {data.maturity_date && (
                <FieldRow
                  label="Дата погашения"
                  value={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <span>{formatDate(data.maturity_date)}</span>
                      {data.days_to_maturity != null && (
                        <Chip
                          label={formatDaysToMaturity(data.days_to_maturity)}
                          size="small"
                          variant="outlined"
                          color="info"
                        />
                      )}
                    </Stack>
                  }
                />
              )}
              {data.placement_date && (
                <FieldRow label="Дата размещения" value={formatDate(data.placement_date)} />
              )}
              {data.coupon_frequency_days != null && (
                <FieldRow
                  label="Периодичность купона"
                  value={`${data.coupon_frequency_days} дн.`}
                  labelTooltip="Количество дней между купонными выплатами"
                />
              )}
            </Section>

            {/* Формула купона */}
            <Section title="Формула купона">
              <FieldRow
                label="Базовый индикатор"
                value={
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Chip
                      label={indicatorNames[data.base_indicator_code] ?? data.base_indicator_code}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                    {indicatorHints[data.base_indicator_code] && (
                      <Tooltip title={indicatorHints[data.base_indicator_code]} arrow>
                        <HelpOutlineIcon fontSize="small" sx={{ color: 'text.secondary', cursor: 'help' }} />
                      </Tooltip>
                    )}
                  </Stack>
                }
              />
              <FieldRow
                label="Спред (Spread)"
                value={
                  data.spread != null ? (
                    <Tooltip title="Надбавка к базовому индикатору" arrow>
                      <span>{data.spread > 0 ? '+' : ''}{data.spread} п.п.</span>
                    </Tooltip>
                  ) : (
                    'Неизвестно'
                  )
                }
              />
              <Stack direction="row" spacing={1} sx={{ mt: 1, mb: 1 }}>
                {data.floor_rate != null && (
                  <Tooltip title="Минимальная ставка купона (floor)" arrow>
                    <Chip label={`Floor: ${data.floor_rate}%`} size="small" color="success" />
                  </Tooltip>
                )}
                {data.cap_rate != null && (
                  <Tooltip title="Максимальная ставка купона (cap)" arrow>
                    <Chip label={`Cap: ${data.cap_rate}%`} size="small" color="warning" />
                  </Tooltip>
                )}
              </Stack>
              {data.extra_indicators && (
                <FieldRow
                  label="Доп. индикаторы"
                  value={data.extra_indicators}
                  labelTooltip="Дополнительные базовые индикаторы при формуле с несколькими индексами"
                />
              )}
              {data.rate_determination_rule && (
                <FieldRow
                  label="Правило фиксации ставки"
                  value={data.rate_determination_rule}
                  labelTooltip="Описание порядка определения ставки купона"
                />
              )}
              {data.formula_raw && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                    Формула (из документации)
                  </Typography>
                  <Box
                    sx={{
                      position: 'relative',
                      bgcolor: 'grey.50',
                      border: 1,
                      borderColor: 'divider',
                      borderRadius: 1,
                      p: 1.5,
                      fontFamily: 'monospace',
                      fontSize: '0.85rem',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {data.formula_raw}
                    <Tooltip title={copied ? 'Скопировано!' : 'Копировать'} arrow>
                      <IconButton
                        size="small"
                        onClick={handleCopyFormula}
                        sx={{ position: 'absolute', top: 4, right: 4 }}
                      >
                        {copied ? <CheckIcon fontSize="small" color="success" /> : <ContentCopyIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              )}
            </Section>

            {/* Механика расчёта */}
            <Section title="Механика расчёта">
              {data.calculation_type && (
                <FieldRow
                  label="Тип расчёта"
                  value={CALCULATION_TYPE_LABELS[data.calculation_type] ?? data.calculation_type}
                  labelTooltip="Тип расчета — это способ определения процентной ставки внутри купонного периода. Он показывает, будет ли ставка меняться ежедневно вслед за рыночными индикаторами (RUONIA, Ключевая ставка) или она зафиксируется в один конкретный момент на весь срок до ближайшей выплаты."
                />
              )}
              {data.accrual_type && (
                <FieldRow
                  label="Тип начисления"
                  value={ACCRUAL_TYPE_LABELS[data.accrual_type] ?? data.accrual_type}
                  labelTooltip="DAILY_ACCRUAL — купон = сумма ежедневных начислений; FIXED_PERIOD — ставка фиксируется на период"
                />
              )}
              <FieldRow
                label="Ежедневное начисление"
                value={
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <span>{data.is_daily_accrual ? '✓' : '✗'}</span>
                    <Typography variant="body2" color={data.is_daily_accrual ? 'success.main' : 'text.secondary'}>
                      {data.is_daily_accrual ? 'Да' : 'Нет'}
                    </Typography>
                  </Stack>
                }
                labelTooltip="Купон рассчитывается как сумма ежедневных начислений (accrual)"
              />
              {data.key_rate_method && (
                <FieldRow
                  label="Метод KEY_RATE"
                  value={KEY_RATE_METHOD_LABELS[data.key_rate_method] ?? data.key_rate_method}
                  labelTooltip="SPOT — значение ключевой ставки на конкретную дату; MA — скользящее среднее за период"
                />
              )}
              {data.interest_compounding && (
                <FieldRow
                  label="Капитализация"
                  value="Применяется"
                  labelTooltip="Используется сложный процент (капитализация)"
                />
              )}
              <FieldRow
                label="Метод наблюдения"
                value={
                  data.observation_type != null
                    ? (observationTypeNames[data.observation_type] ?? data.observation_type)
                    : 'Не определен'
                }
                labelTooltip={data.observation_type != null ? observationTypeHints[data.observation_type] : undefined}
              />
              {data.reference_period_desc && (
                <FieldRow
                  label="Период наблюдения"
                  value={data.reference_period_desc}
                  labelTooltip="Период, за который берётся значение базового индикатора"
                />
              )}
            </Section>

            {/* Технические параметры */}
            <Section title="Технические параметры">
              {data.lookback_period != null && (
                <FieldRow
                  label="Задержка определения ставки"
                  value={`${data.lookback_period} дн.`}
                  labelTooltip="Показывает, за какой день берется рыночная ставка (например, RUONIA). Если стоит '7 дней', то сегодня ваш доход считается по ставке, которая была неделю назад. Это рыночный стандарт, чтобы данные успели официально опубликоваться."
                />
              )}
              {data.lookback_type && (
                <FieldRow
                  label="Тип дней задержки"
                  value={LOOKBACK_LABELS[data.lookback_type] ?? data.lookback_type}
                  labelTooltip="Как считаются дни отступа: календарные (подряд) или только рабочие (банковские) дни."
                />
              )}
              {data.offset_days != null && (
                <FieldRow
                  label="Технический отступ"
                  value={
                    data.lookback_period != null && data.offset_days === data.lookback_period
                      ? `${data.offset_days} дн. (соответствует задержке)`
                      : `${data.offset_days} дн.`
                  }
                  labelTooltip="Это настройка 'математического движка'. Она указывает программе, на сколько дней назад нужно отступить от текущей даты, чтобы найти нужное значение в базе данных. Как правило, это число совпадает с задержкой определения ставки."
                />
              )}
              {data.offset_calendar && (
                <FieldRow
                  label="Тип дней отступа"
                  value={LOOKBACK_LABELS[data.offset_calendar] ?? data.offset_calendar}
                  labelTooltip="Как считаются дни отступа: календарные или рабочие."
                />
              )}
              {data.averaging_period != null && (
                <FieldRow
                  label="Период усреднения"
                  value={`${data.averaging_period} дн.`}
                  labelTooltip="За какой срок (в днях) берется среднее значение индикатора. '0' означает, что берется значение за один конкретный день."
                />
              )}
              {data.day_count && (
                <FieldRow
                  label="Начисление за дни"
                  value={(() => {
                    const dc = String(data.day_count).toUpperCase();
                    const isRealCalendar = dc.includes('ACT/365') || dc.includes('ACT/366');
                    const is30_360 = dc.includes('30/360');
                    return isRealCalendar
                      ? 'По реальному календарю'
                      : is30_360
                        ? 'По 30 дней в месяце'
                        : data.day_count;
                  })()}
                  labelTooltip={
                    (() => {
                      const dc = String(data.day_count).toUpperCase();
                      const isRealCalendar = dc.includes('ACT/365') || dc.includes('ACT/366');
                      const is30_360 = dc.includes('30/360');
                      return isRealCalendar
                        ? DAY_COUNT_REAL_CALENDAR_HINT
                        : is30_360
                          ? DAY_COUNT_30_360_HINT
                          : 'Финансовый стандарт (конвенция), по которому считаются дни в купоне (например, ACT/365 означает фактическое количество дней).';
                    })()
                  }
                />
              )}
              {data.year_base && (
                <FieldRow
                  label="Дней в году"
                  value={`${data.year_base} дн.`}
                  labelTooltip="Какое количество дней берется за основу в формуле (360, 365 или 366)."
                />
              )}
              {data.rounding_precision != null && (
                <FieldRow
                  label="Точность расчета"
                  value={`${data.rounding_precision} знаков`}
                  labelTooltip="До скольких знаков после запятой округляется сумма купона и НКД."
                />
              )}
              {data.fallback && (
                <FieldRow
                  label="Если нет данных"
                  value={FALLBACK_LABELS[data.fallback] ?? data.fallback}
                  labelTooltip="Правило выбора ставки, если на нужную дату она не была опубликована (например, брать за предыдущий рабочий день)."
                />
              )}
            </Section>

            {/* Организатор и листинг */}
            {data.underwriter && (
              <Section title="Организатор и листинг">
                <FieldRow label="Организатор" value={data.underwriter} />
              </Section>
            )}

            {/* Условная логика */}
            {data.condition_logic && (
              <Box
                sx={{
                  mt: 2,
                  p: 2,
                  bgcolor: 'warning.50',
                  border: 1,
                  borderColor: 'warning.light',
                  borderRadius: 1,
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <WarningAmberIcon color="warning" fontSize="small" />
                  <Typography variant="subtitle2" fontWeight={700} color="warning.dark">
                    Условная логика
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {data.condition_logic}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};
