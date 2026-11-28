import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  ClickAwayListener,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Popper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import BarChartIcon from '@mui/icons-material/BarChart';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import CheckIcon from '@mui/icons-material/Check';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloseIcon from '@mui/icons-material/Close';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import LayersIcon from '@mui/icons-material/Layers';
import PercentIcon from '@mui/icons-material/Percent';
import SearchIcon from '@mui/icons-material/Search';
import TuneIcon from '@mui/icons-material/Tune';
import ViewWeekIcon from '@mui/icons-material/ViewWeek';
import { indicatorNames } from './couponTerms';
import { useFiltersStore } from '../../stores/filtersStore';
import type { BondFilters } from '../../types/filters';

type FilterId = 'maturity' | 'yield' | 'coupon' | 'couponYield' | 'rating' | 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing' | 'investorAccess' | 'defaults';
type NumericFilterKey = 'yieldMin' | 'yieldMax' | 'couponMin' | 'couponMax' | 'couponYieldMin' | 'couponYieldMax';
type FilterOption = { label: string; value: string | number };
type FilterChip = { key: string; label: string; onDelete: () => void };

const RATING_OPTIONS = [
  'AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-',
  'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC+', 'CCC', 'CCC-', 'CC', 'C', 'D',
];

const FILTER_OPTIONS: Record<Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, FilterOption[]> = {
  couponMonths: [
    { label: 'Январь', value: 1 }, { label: 'Февраль', value: 2 }, { label: 'Март', value: 3 },
    { label: 'Апрель', value: 4 }, { label: 'Май', value: 5 }, { label: 'Июнь', value: 6 },
    { label: 'Июль', value: 7 }, { label: 'Август', value: 8 }, { label: 'Сентябрь', value: 9 },
    { label: 'Октябрь', value: 10 }, { label: 'Ноябрь', value: 11 }, { label: 'Декабрь', value: 12 },
  ],
  currency: [
    { label: 'RUB', value: 'SUR' }, { label: 'USD', value: 'USD' }, { label: 'EUR', value: 'EUR' },
    { label: 'GBP', value: 'GBP' }, { label: 'CHF', value: 'CHF' },
  ],
  bondType: [
    { label: 'Биржевые', value: 1 }, { label: 'ОФЗ', value: 2 }, { label: 'Корпоративные', value: 3 },
    { label: 'Муниципальные', value: 4 }, { label: 'Региональные', value: 5 },
  ],
  bondKind: [
    { label: 'Амортизируемая', value: 1 }, { label: 'Валютная', value: 2 }, { label: 'Дисконтная', value: 3 },
    { label: 'Конвертируемая', value: 4 }, { label: 'Линкер', value: 5 }, { label: 'Плавающий купон', value: 6 },
    { label: 'Фиксированный купон (известный)', value: 7 }, { label: 'Фиксированный купон (неизвестный)', value: 8 },
    { label: 'Структурная', value: 9 },
  ],
  listing: [
    { label: '1 уровень', value: 1 }, { label: '2 уровень', value: 2 }, { label: '3 уровень', value: 3 },
  ],
};

const FILTER_BUTTONS: Array<{ id: FilterId; label: string; icon: React.ReactNode }> = [
  { id: 'maturity', label: 'Дата погашения', icon: <CalendarMonthIcon /> },
  { id: 'yield', label: 'Доходность', icon: <PercentIcon /> },
  { id: 'rating', label: 'Рейтинг', icon: <LayersIcon /> },
  { id: 'couponMonths', label: 'Месяц выплаты', icon: <ViewWeekIcon /> },
  { id: 'currency', label: 'Валюта', icon: <CurrencyExchangeIcon /> },
  { id: 'bondType', label: 'Тип облигации', icon: <ArticleOutlinedIcon /> },
  { id: 'bondKind', label: 'Вид облигации', icon: <AccountBalanceIcon /> },
  { id: 'listing', label: 'Уровень листинга', icon: <BarChartIcon /> },
  { id: 'investorAccess', label: 'Доступ инвесторам', icon: <AccountBalanceIcon /> },
  { id: 'defaults', label: 'Дефолты', icon: <ArticleOutlinedIcon /> },
];

/** Фильтры, всегда видимые на узких экранах; остальные собраны в «Все фильтры». */
const QUICK_FILTER_IDS: FilterId[] = ['maturity', 'yield', 'rating'];
const SECONDARY_FILTERS = FILTER_BUTTONS.filter((button) => !QUICK_FILTER_IDS.includes(button.id));

const FILTER_KEYS: Array<keyof BondFilters> = [
  'search', 'matdateFrom', 'matdateTo', 'yieldMin', 'yieldMax', 'couponMin', 'couponMax',
  'couponYieldMin', 'couponYieldMax', 'ratingMin', 'ratingMax', 'couponMonths', 'faceunit',
  'bondtype', 'bondtype43', 'listlevel', 'requireCouponBenchmark', 'couponBenchmark', 'spreadMin', 'spreadMax',
    'excludeNonqualifiedInvestors', 'excludeQualifiedInvestors', 'excludeDefaults', 'excludeTechnicalDefaults',
];

/** Тонкий скроллбар в цветах интерфейса вместо системного. */
const thinScrollSx = {
  scrollbarWidth: 'thin',
  scrollbarColor: '#c3cfdf transparent',
  '&::-webkit-scrollbar': { width: 8, height: 8 },
  '&::-webkit-scrollbar-track': { background: 'transparent' },
  '&::-webkit-scrollbar-thumb': { background: '#c3cfdf', borderRadius: 999 },
} as const;

/** Общие размеры полей: 44 px на телефоне для удобного нажатия. */
const fieldSx = {
  '& .MuiOutlinedInput-root': { height: { xs: '2.75rem', md: '2.5rem' } },
  '& .MuiInputBase-input': { fontSize: { xs: '1.05rem', md: '0.9375rem' } },
  '& .MuiInputLabel-root': { fontSize: { xs: '1rem', md: '0.875rem' } },
} as const;

const numberLabel = (value: number): string => value.toLocaleString('ru-RU', { maximumFractionDigits: 2 });

const displayDate = (value: string): string => {
  const [year, month, day] = value.split('-');
  return year && month && day ? `${day}.${month}.${year}` : value;
};

const asInputDate = (date: Date): string => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const datePlusYears = (years: number): string => {
  const result = new Date();
  result.setHours(12, 0, 0, 0);
  result.setFullYear(result.getFullYear() + years);
  return asInputDate(result);
};

const compactLabels = (labels: string[], max = 2): string => {
  if (labels.length <= max) return labels.join(', ');
  return `${labels.slice(0, max).join(', ')} +${labels.length - max}`;
};

const ClearFiltersSvg: React.FC = () => (
  <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="22" height="22" fill="none">
    <path d="m6.5 6.5 11 11m0-11-11 11" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" />
  </svg>
);

const FilterPopoverPaper: React.FC<{ title: string; children: React.ReactNode; width?: number; fluid?: boolean }> = ({ title, children, width = 320, fluid = false }) => (
  <Box sx={{ width: fluid ? '100%' : { xs: `min(${width}px, calc(100vw - 24px))`, sm: width }, p: 1.5, color: '#10264A' }}>
    <Typography sx={{ mb: 1, fontSize: { xs: '1.0625rem', md: '0.95rem' }, fontWeight: 600, color: '#10264A' }}>{title}</Typography>
    {children}
  </Box>
);

const NumericRangeEditor: React.FC<{
  title: string;
  minKey: NumericFilterKey;
  maxKey: NumericFilterKey;
  max: number;
  step: number;
  unit?: string;
  fluid?: boolean;
}> = ({ title, minKey, maxKey, max, step, unit = '%', fluid = false }) => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const minValue = draftFilters[minKey] as number | null;
  const maxValue = draftFilters[maxKey] as number | null;

  const setValue = (key: NumericFilterKey, value: string) => {
    const parsed = value === '' ? null : Number(value);
    setDraftFilter(key, parsed !== null && Number.isFinite(parsed) ? parsed : null);
  };

  return (
    <FilterPopoverPaper title={title} fluid={fluid}>
      <Stack direction="row" spacing={0.75}>
        <TextField
          label="От"
          type="number"
          size="small"
          fullWidth
          value={minValue ?? ''}
          onChange={(event) => setValue(minKey, event.target.value)}
          inputProps={{ min: 0, max, step }}
          sx={fieldSx}
          InputProps={{ endAdornment: unit ? <InputAdornment position="end">{unit}</InputAdornment> : undefined }}
        />
        <TextField
          label="До"
          type="number"
          size="small"
          fullWidth
          value={maxValue ?? ''}
          onChange={(event) => setValue(maxKey, event.target.value)}
          inputProps={{ min: 0, max, step }}
          sx={fieldSx}
          InputProps={{ endAdornment: unit ? <InputAdornment position="end">{unit}</InputAdornment> : undefined }}
        />
      </Stack>
    </FilterPopoverPaper>
  );
};

const MaturityEditor: React.FC<{ fluid?: boolean }> = ({ fluid = false }) => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const [mode, setMode] = useState<'period' | 'presets'>('period');
  const presets = [
    { label: 'До 1 года', from: asInputDate(new Date()), to: datePlusYears(1) },
    { label: '1–3 года', from: datePlusYears(1), to: datePlusYears(3) },
    { label: '3–5 лет', from: datePlusYears(3), to: datePlusYears(5) },
    { label: 'Более 5 лет', from: datePlusYears(5), to: null },
  ];

  return (
    <FilterPopoverPaper title="Дата погашения" width={360} fluid={fluid}>
      <Stack direction="row" spacing={0.5} sx={{ mb: 1 }}>
        <Button size="small" variant={mode === 'period' ? 'contained' : 'text'} onClick={() => setMode('period')} sx={{ minHeight: { xs: '2.75rem', md: '2.25rem' }, px: 0.75, borderRadius: '0.5rem', fontSize: { xs: '1rem', md: '0.875rem' }, textTransform: 'none' }}>
          Период
        </Button>
        <Button size="small" variant={mode === 'presets' ? 'contained' : 'text'} onClick={() => setMode('presets')} sx={{ minHeight: { xs: '2.75rem', md: '2.25rem' }, px: 0.75, borderRadius: '0.5rem', fontSize: { xs: '1rem', md: '0.875rem' }, textTransform: 'none' }}>
          Готовые диапазоны
        </Button>
      </Stack>
      {mode === 'period' ? (
        <Stack direction="row" spacing={0.75}>
          <TextField
            label="С"
            type="date"
            size="small"
            fullWidth
            value={draftFilters.matdateFrom || ''}
            onChange={(event) => setDraftFilter('matdateFrom', event.target.value || null)}
            InputLabelProps={{ shrink: true }}
            sx={{ ...fieldSx, '& .MuiInputBase-input': { fontSize: { xs: '1.05rem', md: '0.9375rem' }, px: 1 } }}
          />
          <TextField
            label="По"
            type="date"
            size="small"
            fullWidth
            value={draftFilters.matdateTo || ''}
            onChange={(event) => setDraftFilter('matdateTo', event.target.value || null)}
            InputLabelProps={{ shrink: true }}
            sx={{ ...fieldSx, '& .MuiInputBase-input': { fontSize: { xs: '1.05rem', md: '0.9375rem' }, px: 1 } }}
          />
        </Stack>
      ) : (
        <Stack direction="row" flexWrap="wrap" gap={0.75}>
          {presets.map((preset) => (
            <Button
              key={preset.label}
              size="small"
              variant="outlined"
              onClick={() => {
                setDraftFilter('matdateFrom', preset.from);
                setDraftFilter('matdateTo', preset.to);
              }}
              sx={{ minHeight: { xs: '2.75rem', md: '2.25rem' }, px: 1, borderRadius: '0.5rem', textTransform: 'none', fontSize: { xs: '1rem', md: '0.875rem' } }}
            >
              {preset.label}
            </Button>
          ))}
        </Stack>
      )}
    </FilterPopoverPaper>
  );
};

const RatingEditor: React.FC<{ fluid?: boolean }> = ({ fluid = false }) => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const [openBound, setOpenBound] = useState<'min' | 'max' | null>(null);

  const renderBound = (bound: 'min' | 'max', label: string, value: string | null) => {
    const isOpen = openBound === bound;
    const otherBoundValue = bound === 'min' ? draftFilters.ratingMax : draftFilters.ratingMin;
    const otherBoundIndex = otherBoundValue === null ? -1 : RATING_OPTIONS.indexOf(otherBoundValue);
    const availableRatings = RATING_OPTIONS.filter((rating) => {
      const ratingIndex = RATING_OPTIONS.indexOf(rating);
      if (otherBoundIndex < 0) return true;
      return bound === 'min' ? ratingIndex >= otherBoundIndex : ratingIndex <= otherBoundIndex;
    });

    const selectValue = (rating: string | null) => {
      if (bound === 'min') {
        setDraftFilter('ratingMin', rating);
        if (rating && draftFilters.ratingMax
          && RATING_OPTIONS.indexOf(draftFilters.ratingMax) > RATING_OPTIONS.indexOf(rating)) {
          setDraftFilter('ratingMax', null);
        }
      } else {
        setDraftFilter('ratingMax', rating);
        if (rating && draftFilters.ratingMin
          && RATING_OPTIONS.indexOf(rating) > RATING_OPTIONS.indexOf(draftFilters.ratingMin)) {
          setDraftFilter('ratingMin', null);
        }
      }
      setOpenBound(null);
    };

    return (
      <Box key={bound} sx={{ minWidth: 0 }}>
        <Typography sx={{ mb: 0.45, fontSize: { xs: '0.9375rem', md: '0.875rem' }, fontWeight: 600, color: '#42526B' }}>{label}</Typography>
        <Button
          fullWidth
          variant="outlined"
          aria-label={`${label}: ${value ?? 'Без ограничений'}`}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-controls={isOpen ? `rating-${bound}-listbox` : undefined}
          onClick={() => setOpenBound((current) => current === bound ? null : bound)}
          endIcon={<ExpandMoreIcon sx={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 120ms ease' }} />}
          sx={{
            minHeight: { xs: '2.75rem', md: '2.5rem' },
            justifyContent: 'space-between',
            px: 1.1,
            borderColor: isOpen ? 'primary.main' : 'rgba(134,164,205,0.45)',
            borderRadius: '0.5rem',
            bgcolor: 'rgba(255,255,255,0.9)',
            color: '#10264A',
            fontSize: { xs: '1rem', md: '0.9rem' },
            textTransform: 'none',
            '& .MuiButton-endIcon': { ml: 0.5 },
          }}
        >
          {value ?? 'Без ограничений'}
        </Button>
        {isOpen && (
          <Box
            id={`rating-${bound}-listbox`}
            role="listbox"
            aria-label={`${label} рейтинг`}
            sx={{
              mt: 0.5,
              maxHeight: { xs: 220, md: 180 },
              overflowY: 'auto',
              overscrollBehavior: 'contain',
              border: '1px solid rgba(134,164,205,0.32)',
              borderRadius: '0.5rem',
              bgcolor: '#fff',
              boxShadow: '0 6px 16px rgba(40,70,120,0.10)',
              ...thinScrollSx,
            }}
          >
            {[{ label: 'Без ограничений', value: null }, ...availableRatings.map((rating) => ({ label: rating, value: rating }))].map((option) => {
              const selected = option.value === value;
              return (
                <Box
                  key={option.label}
                  component="button"
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => selectValue(option.value)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    width: '100%',
                    minHeight: { xs: 44, md: 34 },
                    px: 1,
                    border: 0,
                    bgcolor: selected ? 'rgba(25,118,210,0.10)' : 'transparent',
                    color: selected ? 'primary.dark' : '#10264A',
                    textAlign: 'left',
                    font: 'inherit',
                    fontSize: { xs: '1rem', md: '0.9rem' },
                    cursor: 'pointer',
                    '&:hover, &:focus-visible': { bgcolor: 'rgba(25,118,210,0.08)', outline: 'none' },
                  }}
                >
                  {option.label}
                </Box>
              );
            })}
          </Box>
        )}
      </Box>
    );
  };

  return (
    <FilterPopoverPaper title="Кредитный рейтинг" width={270} fluid={fluid}>
      <Stack
        spacing={0.75}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && openBound) {
            event.stopPropagation();
            setOpenBound(null);
          }
        }}
      >
        {renderBound('min', 'От', draftFilters.ratingMin)}
        {renderBound('max', 'До', draftFilters.ratingMax)}
      </Stack>
    </FilterPopoverPaper>
  );
};

const popoverWidthFor = (title: string): number => (
  title === 'Уровень листинга' ? 220
    : title === 'Валюта' ? 230
      : title === 'Тип облигации' ? 260
        : title === 'Вид облигации' ? 285
          : 260
);

const CheckboxListEditor: React.FC<{
  title: string;
  options: FilterOption[];
  selected: Array<string | number>;
  onToggle: (value: string | number) => void;
  fluid?: boolean;
}> = ({ title, options, selected, onToggle, fluid = false }) => (
  <FilterPopoverPaper title={title} width={popoverWidthFor(title)} fluid={fluid}>
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: title === 'Месяц выплаты' ? 'repeat(2, minmax(0, 1fr))' : '1fr',
      columnGap: title === 'Месяц выплаты' ? 1 : 0,
      maxHeight: { xs: 260, md: 230 },
      overflowY: 'auto',
      overscrollBehavior: 'contain',
      mx: -0.5,
      ...thinScrollSx,
    }}>
      {options.map((option) => (
        <FormControlLabel
          key={option.value}
          control={<Checkbox size="small" checked={selected.includes(option.value)} onChange={() => onToggle(option.value)} sx={{ p: 0.5, mr: 0.4 }} />}
          label={option.label}
          sx={{
            display: 'flex',
            mx: 0,
            my: 0,
            minHeight: { xs: 44, md: 34 },
            '& .MuiFormControlLabel-label': { fontSize: { xs: '1rem', md: '0.9rem' }, lineHeight: 1.35, color: '#10264A' },
          }}
        />
      ))}
    </Box>
  </FilterPopoverPaper>
);

const BondMarketFilters: React.FC = () => {
  const { filters, draftFilters, setDraftFilter, applyFilters, resetFilters } = useFiltersStore();
  const [openFilter, setOpenFilter] = useState<{ id: FilterId; anchor: HTMLElement } | null>(null);
  const [allFiltersAnchor, setAllFiltersAnchor] = useState<HTMLElement | null>(null);
  const [allFiltersView, setAllFiltersView] = useState<FilterId | null>(null);

  const isDirty = useMemo(() => FILTER_KEYS.some((key) => {
    const activeValue = filters[key];
    const draftValue = draftFilters[key];
    return Array.isArray(activeValue) && Array.isArray(draftValue)
      ? activeValue.length !== draftValue.length || activeValue.some((value, index) => value !== draftValue[index])
      : activeValue !== draftValue;
  }), [filters, draftFilters]);

  const invalidRanges = useMemo(() => {
    const ranges: Array<[number | null, number | null, number]> = [
      [draftFilters.yieldMin, draftFilters.yieldMax, 30],
      [draftFilters.couponMin, draftFilters.couponMax, 30],
      [draftFilters.couponYieldMin, draftFilters.couponYieldMax, 100],
    ];
    const invalidNumber = ranges.some(([min, max, upper]) =>
      (min !== null && (min < 0 || min > upper))
      || (max !== null && (max < 0 || max > upper))
      || (min !== null && max !== null && min > max),
    );
    const invalidDate = Boolean(draftFilters.matdateFrom && draftFilters.matdateTo && draftFilters.matdateFrom > draftFilters.matdateTo);
    const invalidRating = draftFilters.ratingMin !== null && draftFilters.ratingMax !== null
      && RATING_OPTIONS.indexOf(draftFilters.ratingMax) > RATING_OPTIONS.indexOf(draftFilters.ratingMin);

    return invalidNumber || invalidDate || invalidRating;
  }, [draftFilters]);

  const hiddenFilterActive = useCallback((id: FilterId): boolean => {
    switch (id) {
      case 'couponMonths': return draftFilters.couponMonths.length > 0;
      case 'currency': return draftFilters.faceunit.length > 0;
      case 'bondType': return draftFilters.bondtype.length > 0;
      case 'bondKind': return draftFilters.bondtype43.length > 0;
      case 'listing': return draftFilters.listlevel.length > 0;
      case 'investorAccess': return draftFilters.excludeNonqualifiedInvestors || draftFilters.excludeQualifiedInvestors;
      case 'defaults': return draftFilters.excludeDefaults || draftFilters.excludeTechnicalDefaults;
      default: return false;
    }
  }, [draftFilters]);

  const hiddenActiveCount = useMemo(
    () => SECONDARY_FILTERS.filter((button) => hiddenFilterActive(button.id)).length,
    [hiddenFilterActive],
  );

  const toggleFilter = useCallback((id: FilterId, anchor: HTMLElement) => {
    setOpenFilter((current) => current?.id === id ? null : { id, anchor });
  }, []);

  const closeAllPopovers = useCallback(() => {
    setOpenFilter(null);
    setAllFiltersAnchor(null);
    setAllFiltersView(null);
  }, []);

  const handleClickAway = useCallback((event: MouseEvent | TouchEvent) => {
    const target = event.target;
    if (target instanceof Element && target.closest('.MuiMenu-root, .MuiPopover-root, [data-bond-filter-popover]')) return;
    closeAllPopovers();
  }, [closeAllPopovers]);

  useEffect(() => {
    if (!openFilter && !allFiltersAnchor) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeAllPopovers();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closeAllPopovers, openFilter, allFiltersAnchor]);

  const handleReset = useCallback(() => {
    resetFilters();
    closeAllPopovers();
  }, [closeAllPopovers, resetFilters]);

  const handleApply = useCallback(() => {
    applyFilters();
    closeAllPopovers();
  }, [applyFilters, closeAllPopovers]);

  const toggleArrayValue = useCallback((id: Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, value: string | number) => {
    if (id === 'couponMonths') {
      const item = Number(value);
      const values = draftFilters.couponMonths;
      setDraftFilter('couponMonths', values.includes(item) ? values.filter((entry) => entry !== item) : [...values, item].sort((a, b) => a - b));
    } else if (id === 'currency') {
      const item = String(value);
      const values = draftFilters.faceunit;
      setDraftFilter('faceunit', values.includes(item) ? values.filter((entry) => entry !== item) : [...values, item]);
    } else if (id === 'bondType') {
      const item = Number(value);
      const values = draftFilters.bondtype;
      setDraftFilter('bondtype', values.includes(item) ? values.filter((entry) => entry !== item) : [...values, item]);
    } else if (id === 'bondKind') {
      const item = Number(value);
      const values = draftFilters.bondtype43;
      setDraftFilter('bondtype43', values.includes(item) ? values.filter((entry) => entry !== item) : [...values, item]);
    } else {
      const item = Number(value);
      const values = draftFilters.listlevel;
      setDraftFilter('listlevel', values.includes(item) ? values.filter((entry) => entry !== item) : [...values, item]);
    }
  }, [draftFilters, setDraftFilter]);

  const selectedFor = useCallback((id: Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>): Array<string | number> => {
    if (id === 'couponMonths') return draftFilters.couponMonths;
    if (id === 'currency') return draftFilters.faceunit;
    if (id === 'bondType') return draftFilters.bondtype;
    if (id === 'bondKind') return draftFilters.bondtype43;
    return draftFilters.listlevel;
  }, [draftFilters]);

  const clearFilter = useCallback((id: FilterId) => {
    switch (id) {
      case 'maturity':
        setDraftFilter('matdateFrom', null);
        setDraftFilter('matdateTo', null);
        break;
      case 'yield':
        setDraftFilter('yieldMin', null);
        setDraftFilter('yieldMax', null);
        break;
      case 'coupon':
        setDraftFilter('couponMin', null);
        setDraftFilter('couponMax', null);
        break;
      case 'couponYield':
        setDraftFilter('couponYieldMin', null);
        setDraftFilter('couponYieldMax', null);
        break;
      case 'rating':
        setDraftFilter('ratingMin', null);
        setDraftFilter('ratingMax', null);
        break;
      case 'couponMonths': setDraftFilter('couponMonths', []); break;
      case 'currency': setDraftFilter('faceunit', []); break;
      case 'bondType': setDraftFilter('bondtype', []); break;
      case 'bondKind': setDraftFilter('bondtype43', []); break;
      case 'listing': setDraftFilter('listlevel', []); break;
      case 'investorAccess': setDraftFilter('excludeNonqualifiedInvestors', false); setDraftFilter('excludeQualifiedInvestors', false); break;
      case 'defaults': setDraftFilter('excludeDefaults', false); setDraftFilter('excludeTechnicalDefaults', false); break;
    }
  }, [setDraftFilter]);

  const chips = useMemo<FilterChip[]>(() => {
    const result: FilterChip[] = [];
    const addRangeChip = (id: FilterId, label: string, min: number | null, max: number | null, unit = '%') => {
      if (min === null && max === null) return;
      const value = min !== null && max !== null
        ? `${numberLabel(min)}–${numberLabel(max)}${unit}`
        : min !== null ? `от ${numberLabel(min)}${unit}` : `до ${numberLabel(max as number)}${unit}`;
      result.push({ key: id, label: `${label}: ${value}`, onDelete: () => clearFilter(id) });
    };
    const labelsFor = (id: Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>) => {
      const selected = selectedFor(id);
      return FILTER_OPTIONS[id].filter((option) => selected.includes(option.value)).map((option) => option.label);
    };

    if (draftFilters.requireCouponBenchmark || draftFilters.couponBenchmark?.length) {
      const names = draftFilters.couponBenchmark?.map(code => indicatorNames[code] ?? code);
      result.push({
        key: 'benchmark', label: `База купона: ${names?.length ? names.join(', ') : 'любая известная'}`,
        onDelete: () => {
          setDraftFilter('couponBenchmark', undefined);
          setDraftFilter('requireCouponBenchmark', undefined);
        },
      });
    }
    if (draftFilters.spreadMin != null || draftFilters.spreadMax != null) {
      const bounds = [
        draftFilters.spreadMin != null && `от ${numberLabel(draftFilters.spreadMin)}`,
        draftFilters.spreadMax != null && `до ${numberLabel(draftFilters.spreadMax)}`,
      ].filter(Boolean).join(' ');
      result.push({ key: 'spread', label: `Премия ${bounds} п.п.`, onDelete: () => {
        setDraftFilter('spreadMin', undefined);
        setDraftFilter('spreadMax', undefined);
      } });
    }
    if (draftFilters.matdateFrom || draftFilters.matdateTo) {
      const from = draftFilters.matdateFrom ? displayDate(draftFilters.matdateFrom) : 'любая дата';
      const to = draftFilters.matdateTo ? displayDate(draftFilters.matdateTo) : 'без ограничения';
      result.push({ key: 'maturity', label: `Погашение: ${from} — ${to}`, onDelete: () => clearFilter('maturity') });
    }
    addRangeChip('yield', 'Доходность к погашению (YTM)', draftFilters.yieldMin, draftFilters.yieldMax);
    addRangeChip('coupon', 'Купонная доходность к номиналу', draftFilters.couponMin, draftFilters.couponMax);
    addRangeChip('couponYield', 'Купонная доходность к цене', draftFilters.couponYieldMin, draftFilters.couponYieldMax);
    if (draftFilters.ratingMin || draftFilters.ratingMax) {
      result.push({
        key: 'rating',
        label: `Рейтинг: ${draftFilters.ratingMin ?? 'любой'} — ${draftFilters.ratingMax ?? 'любой'}`,
        onDelete: () => clearFilter('rating'),
      });
    }
    if (draftFilters.excludeNonqualifiedInvestors || draftFilters.excludeQualifiedInvestors) result.push({ key: 'investorAccess', label: `Исключить доступ: ${[draftFilters.excludeNonqualifiedInvestors && 'неквалифицированным', draftFilters.excludeQualifiedInvestors && 'квалифицированным'].filter(Boolean).join(', ')}`, onDelete: () => clearFilter('investorAccess') });
    if (draftFilters.excludeDefaults || draftFilters.excludeTechnicalDefaults) result.push({ key: 'defaults', label: `Исключить: ${[draftFilters.excludeDefaults && 'дефолт', draftFilters.excludeTechnicalDefaults && 'технический дефолт'].filter(Boolean).join(', ')}`, onDelete: () => clearFilter('defaults') });

    const groupLabels: Array<[Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, string]> = [
      ['couponMonths', 'Выплата в любом будущем году'], ['currency', 'Валюта'], ['bondType', 'Тип'], ['bondKind', 'Вид'], ['listing', 'Листинг'],
    ];
    groupLabels.forEach(([id, title]) => {
      const labels = labelsFor(id);
      if (labels.length > 0) result.push({ key: id, label: `${title}: ${compactLabels(labels)}`, onDelete: () => clearFilter(id) });
    });
    return result;
  }, [clearFilter, draftFilters, selectedFor, setDraftFilter]);

  const renderPopoverContent = (id: FilterId, fluid = false) => {
    switch (id) {
      case 'maturity': return <MaturityEditor fluid={fluid} />;
      case 'yield': return (
        <Stack spacing={1} sx={{ width: fluid ? '100%' : { xs: 'min(360px, calc(100vw - 24px))', sm: 360 } }}>
          <NumericRangeEditor fluid={fluid} title="Купонная доходность к номиналу" minKey="couponMin" maxKey="couponMax" max={30} step={0.5} />
          <NumericRangeEditor fluid={fluid} title="Купонная доходность к цене" minKey="couponYieldMin" maxKey="couponYieldMax" max={100} step={0.1} />
          <NumericRangeEditor fluid={fluid} title="Доходность к погашению (YTM)" minKey="yieldMin" maxKey="yieldMax" max={30} step={0.1} />
        </Stack>
      );
      case 'coupon': return <NumericRangeEditor fluid={fluid} title="Купонная доходность к номиналу" minKey="couponMin" maxKey="couponMax" max={30} step={0.5} />;
      case 'couponYield': return <NumericRangeEditor fluid={fluid} title="Купонная доходность к цене" minKey="couponYieldMin" maxKey="couponYieldMax" max={100} step={0.1} />;
      case 'rating': return <RatingEditor fluid={fluid} />;
      case 'investorAccess':
      case 'defaults': {
        const choices: Array<[keyof BondFilters, string]> = id === 'investorAccess'
          ? [['excludeNonqualifiedInvestors', 'Для неквалифицированных инвесторов'], ['excludeQualifiedInvestors', 'Для квалифицированных инвесторов']]
          : [['excludeDefaults', 'Был дефолт'], ['excludeTechnicalDefaults', 'Был технический дефолт']];
        return <Stack sx={{ p: 1.5, minWidth: fluid ? 0 : 280, width: fluid ? '100%' : 'auto' }} spacing={0.5}>
          <Typography sx={{ fontSize: { xs: '1.0625rem', md: '0.95rem' }, fontWeight: 700, color: '#10264A' }}>Исключить из поиска</Typography>
          {choices.map(([key, label]) => (
            <FormControlLabel
              key={key}
              control={<Checkbox checked={Boolean(draftFilters[key])} onChange={(_, checked) => setDraftFilter(key, checked)} />}
              label={label}
              sx={{ minHeight: { xs: 44, md: 36 }, '& .MuiFormControlLabel-label': { fontSize: { xs: '1rem', md: '0.9rem' } } }}
            />
          ))}
        </Stack>;
      }
      case 'couponMonths':
      case 'currency':
      case 'bondType':
      case 'bondKind':
      case 'listing':
        return (
          <CheckboxListEditor
            title={FILTER_BUTTONS.find((button) => button.id === id)?.label ?? 'Фильтр'}
            options={FILTER_OPTIONS[id]}
            selected={selectedFor(id)}
            fluid={fluid}
            onToggle={(value) => toggleArrayValue(id as Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, value)}
          />
        );
      default: return null;
    }
  };

  const triggerSx = (isOpen: boolean) => ({
    minHeight: { xs: '2.75rem', md: '2.25rem' },
    px: { xs: 1, md: 1 },
    borderRadius: '0.5rem',
    borderColor: isOpen ? 'primary.main' : 'rgba(134,164,205,0.45)',
    bgcolor: isOpen ? 'rgba(25,118,210,0.10)' : 'rgba(255,255,255,0.88)',
    color: isOpen ? 'primary.dark' : '#10264A',
    fontSize: { xs: '1rem', md: '0.875rem' },
    fontWeight: 500,
    whiteSpace: 'nowrap',
    textTransform: 'none',
    boxShadow: isOpen ? '0 0 0 2px rgba(25,118,210,0.12)' : 'none',
    '&:hover': { borderColor: 'primary.light', bgcolor: 'rgba(25,118,210,0.06)' },
    '& .MuiButton-startIcon': { mr: 0.55, '& svg': { fontSize: 17 } },
    '& .MuiButton-endIcon': { ml: 0.35, '& svg': { fontSize: 16 } },
  } as const);

  return (
    <ClickAwayListener onClickAway={handleClickAway}>
      <Box
        component="section"
        aria-label="Фильтры рынка облигаций"
        onClickCapture={(event) => {
          const target = event.target as HTMLElement;
          if (
            target.closest('[data-bond-filter-trigger]')
            || target.closest('[data-bond-filter-popover]')
            || !event.currentTarget.contains(target)
          ) return;
          closeAllPopovers();
        }}
        sx={{
          position: 'relative',
          zIndex: 2,
          flex: '0 0 auto',
          p: { xs: 1.25, sm: 1.5 },
          border: '1px solid rgba(255,255,255,0.92)',
          borderRadius: '1rem',
          bgcolor: 'rgba(255,255,255,0.82)',
          boxShadow: '0 4px 14px rgba(61,99,160,0.08), inset 0 1px 0 rgba(255,255,255,0.9)',
          backdropFilter: 'blur(14px) saturate(130%)',
        }}
      >
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: { xs: 0.75, md: 0.75 },
      }}>
        <TextField
          size="small"
          placeholder="Поиск по коду, названию или ISIN"
          value={draftFilters.search}
          onChange={(event) => setDraftFilter('search', event.target.value)}
          sx={{
            flex: '1 1 14rem',
            maxWidth: { md: '20rem' },
            '& .MuiOutlinedInput-root': { height: { xs: '2.75rem', md: '2.5rem' }, borderRadius: '0.5rem', bgcolor: 'rgba(255,255,255,0.9)' },
            '& .MuiInputBase-input': { fontSize: { xs: '1.05rem', md: '0.9375rem' } },
          }}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon sx={{ color: '#42526B', fontSize: 18 }} /></InputAdornment>,
            endAdornment: draftFilters.search ? (
              <InputAdornment position="end">
                <IconButton size="small" aria-label="Очистить поиск" onClick={() => setDraftFilter('search', '')} edge="end">
                  <CloseIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </InputAdornment>
            ) : undefined,
          }}
          inputProps={{ 'aria-label': 'Поиск по коду, названию или ISIN' }}
        />

        {FILTER_BUTTONS.map((filter) => {
          const isOpen = openFilter?.id === filter.id;
          const isQuick = QUICK_FILTER_IDS.includes(filter.id);
          return (
            <Button
              key={filter.id}
              data-bond-filter-trigger="true"
              size="small"
              variant="outlined"
              startIcon={filter.icon}
              endIcon={isOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              onClick={(event) => toggleFilter(filter.id, event.currentTarget)}
              aria-haspopup="dialog"
              aria-expanded={isOpen}
              aria-controls={isOpen ? `bond-filter-popover-${filter.id}` : undefined}
              sx={{ ...triggerSx(isOpen), display: isQuick ? 'inline-flex' : { xs: 'none', md: 'inline-flex' } }}
            >
              {filter.label}
            </Button>
          );
        })}

        <Button
          data-bond-filter-trigger="true"
          size="small"
          variant="outlined"
          startIcon={<TuneIcon />}
          endIcon={allFiltersAnchor ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          onClick={(event) => {
            setOpenFilter(null);
            setAllFiltersView(null);
            setAllFiltersAnchor((current) => current ? null : event.currentTarget);
          }}
          aria-haspopup="dialog"
          aria-expanded={Boolean(allFiltersAnchor)}
          aria-controls={allFiltersAnchor ? 'bond-all-filters-popover' : undefined}
          sx={{ ...triggerSx(Boolean(allFiltersAnchor) || hiddenActiveCount > 0), display: { xs: 'inline-flex', md: 'none' } }}
        >
          {hiddenActiveCount > 0 ? `Все фильтры · ${hiddenActiveCount}` : 'Все фильтры'}
        </Button>
      </Box>

      {isDirty && (
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 1, flexWrap: 'wrap' }}>
          <Button
            size="small"
            variant="contained"
            startIcon={<CheckIcon />}
            disabled={invalidRanges}
            onClick={handleApply}
            sx={{
              minHeight: { xs: '2.75rem', md: '2.25rem' },
              px: 1.5,
              borderRadius: '0.5rem',
              textTransform: 'none',
              fontSize: { xs: '1rem', md: '0.875rem' },
              boxShadow: 'none',
            }}
          >
            Применить
          </Button>
          <Button
            size="small"
            variant="text"
            onClick={handleReset}
            sx={{
              minHeight: { xs: '2.75rem', md: '2.25rem' },
              px: 1,
              borderRadius: '0.5rem',
              textTransform: 'none',
              fontSize: { xs: '1rem', md: '0.875rem' },
              color: '#B3261E',
              '&:hover': { bgcolor: 'rgba(179,38,30,0.08)' },
            }}
          >
            Сбросить
          </Button>
        </Stack>
      )}

      {chips.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.75, mt: 1 }}>
          {chips.map((chip) => (
            <Chip
              key={chip.key}
              label={chip.label}
              size="small"
              onDelete={chip.onDelete}
              deleteIcon={<CloseIcon />}
              sx={{
                height: { xs: 34, md: 28 },
                pl: 0.5,
                border: '1px solid rgba(25,118,210,0.28)',
                bgcolor: 'rgba(25,118,210,0.10)',
                color: '#0F4C96',
                fontSize: { xs: '0.9375rem', md: '0.875rem' },
                fontWeight: 500,
                '& .MuiChip-deleteIcon': { color: '#0F4C96', fontSize: 18, '&:hover': { color: '#0A3A73' } },
              }}
            />
          ))}
          {!isDirty && (
            <IconButton
              size="small"
              disableRipple
              title="Очистить все фильтры"
              aria-label="Очистить все фильтры"
              onClick={handleReset}
              sx={{
                width: { xs: 34, md: 30 },
                height: { xs: 34, md: 28 },
                p: 0,
                ml: 'auto',
                borderRadius: '0.5rem',
                color: '#B3261E',
                bgcolor: 'transparent',
                '&:hover': { bgcolor: 'rgba(179,38,30,0.08)' },
                '&:focus-visible': { outline: '2px solid rgba(179,38,30,0.45)', outlineOffset: 1 },
              }}
            >
              <ClearFiltersSvg />
            </IconButton>
          )}
        </Box>
      )}

      {invalidRanges && (
        <Typography role="alert" sx={{ mt: 0.75, fontSize: { xs: '0.9375rem', md: '0.875rem' }, color: '#B3261E' }}>
          Проверьте границы диапазона и даты погашения.
        </Typography>
      )}

      {openFilter && (() => {
        const { id, anchor } = openFilter;
        const filter = FILTER_BUTTONS.find((item) => item.id === id);
        if (!filter) return null;
        return (
          <Popper
            key={id}
            open
            anchorEl={anchor}
            placement="bottom-start"
            modifiers={[
              { name: 'flip', options: { fallbackPlacements: ['bottom-end', 'top-start', 'top-end'] } },
              { name: 'preventOverflow', options: { padding: 12 } },
            ]}
            sx={{ zIndex: 1400 }}
          >
            <Box sx={{ mt: 0.5, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.94)', borderRadius: '0.75rem', bgcolor: 'rgba(255,255,255,0.97)', boxShadow: '0 12px 30px rgba(40,70,120,0.17)', backdropFilter: 'blur(22px)' }}>
              <Box id={`bond-filter-popover-${id}`} role="dialog" aria-label={filter.label} data-bond-filter-popover="true">
                {renderPopoverContent(id)}
              </Box>
            </Box>
          </Popper>
        );
      })()}

      {allFiltersAnchor && (
        <Popper
          open
          anchorEl={allFiltersAnchor}
          placement="bottom-start"
          modifiers={[
            { name: 'flip', options: { fallbackPlacements: ['bottom-end', 'top-start', 'top-end'] } },
            { name: 'preventOverflow', options: { padding: 12 } },
          ]}
          sx={{ zIndex: 1400 }}
        >
          <Box sx={{ mt: 0.5, width: { xs: 'min(20rem, calc(100vw - 1.5rem))', sm: '21rem' }, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.94)', borderRadius: '0.75rem', bgcolor: 'rgba(255,255,255,0.97)', boxShadow: '0 12px 30px rgba(40,70,120,0.17)', backdropFilter: 'blur(22px)' }}>
            <Box id="bond-all-filters-popover" role="dialog" aria-label="Все фильтры" data-bond-filter-popover="true" sx={{ p: 1 }}>
              {allFiltersView === null ? (
                <>
                  <Typography sx={{ px: 1, pt: 0.5, pb: 0.75, fontSize: '1.0625rem', fontWeight: 600, color: '#10264A' }}>
                    Все фильтры
                  </Typography>
                  <Stack spacing={0.25}>
                    {SECONDARY_FILTERS.map((filter) => {
                      const isActive = hiddenFilterActive(filter.id);
                      return (
                        <Button
                          key={filter.id}
                          fullWidth
                          onClick={() => setAllFiltersView(filter.id)}
                          startIcon={filter.icon}
                          endIcon={<ChevronRightIcon />}
                          sx={{
                            justifyContent: 'flex-start',
                            minHeight: 44,
                            px: 1,
                            borderRadius: '0.5rem',
                            color: isActive ? 'primary.dark' : '#10264A',
                            bgcolor: isActive ? 'rgba(25,118,210,0.08)' : 'transparent',
                            fontSize: '1rem',
                            fontWeight: isActive ? 600 : 500,
                            textTransform: 'none',
                            '& .MuiButton-endIcon': { ml: 'auto' },
                          }}
                        >
                          {filter.label}
                        </Button>
                      );
                    })}
                  </Stack>
                  {isDirty && (
                    <Stack direction="row" spacing={0.75} sx={{ mt: 1 }}>
                      <Button
                        fullWidth
                        size="small"
                        variant="contained"
                        startIcon={<CheckIcon />}
                        disabled={invalidRanges}
                        onClick={handleApply}
                        sx={{ minHeight: 44, borderRadius: '0.5rem', textTransform: 'none', fontSize: '1rem', boxShadow: 'none' }}
                      >
                        Применить
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        onClick={handleReset}
                        sx={{ minHeight: 44, borderRadius: '0.5rem', textTransform: 'none', fontSize: '1rem', color: '#B3261E' }}
                      >
                        Сбросить
                      </Button>
                    </Stack>
                  )}
                </>
              ) : (
                <>
                  <Button
                    onClick={() => setAllFiltersView(null)}
                    startIcon={<ArrowBackIcon />}
                    sx={{ justifyContent: 'flex-start', minHeight: 40, px: 0.75, mb: 0.5, borderRadius: '0.5rem', color: '#42526B', fontSize: '0.9375rem', textTransform: 'none' }}
                  >
                    Все фильтры
                  </Button>
                  {renderPopoverContent(allFiltersView, true)}
                  {isDirty && (
                    <Stack direction="row" spacing={0.75} sx={{ px: 1.5, pb: 1.5 }}>
                      <Button
                        fullWidth
                        size="small"
                        variant="contained"
                        startIcon={<CheckIcon />}
                        disabled={invalidRanges}
                        onClick={handleApply}
                        sx={{ minHeight: 44, borderRadius: '0.5rem', textTransform: 'none', fontSize: '1rem', boxShadow: 'none' }}
                      >
                        Применить
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        onClick={handleReset}
                        sx={{ minHeight: 44, borderRadius: '0.5rem', textTransform: 'none', fontSize: '1rem', color: '#B3261E' }}
                      >
                        Сбросить
                      </Button>
                    </Stack>
                  )}
                </>
              )}
            </Box>
          </Box>
        </Popper>
      )}
      </Box>
    </ClickAwayListener>
  );
};

export default BondMarketFilters;
