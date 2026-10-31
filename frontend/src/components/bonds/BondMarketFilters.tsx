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
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import BarChartIcon from '@mui/icons-material/BarChart';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import CloseIcon from '@mui/icons-material/Close';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import LayersIcon from '@mui/icons-material/Layers';
import PaymentsIcon from '@mui/icons-material/Payments';
import PercentIcon from '@mui/icons-material/Percent';
import SearchIcon from '@mui/icons-material/Search';
import ViewWeekIcon from '@mui/icons-material/ViewWeek';
import { useFiltersStore } from '../../stores/filtersStore';
import type { BondFilters } from '../../types/filters';

type FilterId = 'maturity' | 'yield' | 'coupon' | 'couponYield' | 'rating' | 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing';
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
  { id: 'coupon', label: 'Купон', icon: <PaymentsIcon /> },
  { id: 'couponYield', label: 'Купонная доходность', icon: <PercentIcon /> },
  { id: 'rating', label: 'Рейтинг', icon: <LayersIcon /> },
  { id: 'couponMonths', label: 'Месяц выплаты', icon: <ViewWeekIcon /> },
  { id: 'currency', label: 'Валюта', icon: <CurrencyExchangeIcon /> },
  { id: 'bondType', label: 'Тип облигации', icon: <ArticleOutlinedIcon /> },
  { id: 'bondKind', label: 'Вид облигации', icon: <AccountBalanceIcon /> },
  { id: 'listing', label: 'Уровень листинга', icon: <BarChartIcon /> },
];

const FILTER_KEYS: Array<keyof BondFilters> = [
  'search', 'matdateFrom', 'matdateTo', 'yieldMin', 'yieldMax', 'couponMin', 'couponMax',
  'couponYieldMin', 'couponYieldMax', 'ratingMin', 'ratingMax', 'couponMonths', 'faceunit',
  'bondtype', 'bondtype43', 'listlevel',
];

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

const FilterPopoverPaper: React.FC<{ title: string; children: React.ReactNode; width?: number }> = ({ title, children, width = 320 }) => (
  <Box sx={{ width: { xs: `min(${width}px, calc(100vw - 24px))`, sm: width }, p: 1.5, color: '#142B4D' }}>
    <Typography sx={{ mb: 1, fontSize: '0.95rem', fontWeight: 600, color: '#142B4D' }}>{title}</Typography>
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
}> = ({ title, minKey, maxKey, max, step, unit = '%' }) => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const minValue = draftFilters[minKey] as number | null;
  const maxValue = draftFilters[maxKey] as number | null;

  const setValue = (key: NumericFilterKey, value: string) => {
    const parsed = value === '' ? null : Number(value);
    setDraftFilter(key, parsed !== null && Number.isFinite(parsed) ? parsed : null);
  };

  return (
    <FilterPopoverPaper title={title}>
      <Stack direction="row" spacing={0.75}>
        <TextField
          label="От"
          type="number"
          size="small"
          fullWidth
          value={minValue ?? ''}
          onChange={(event) => setValue(minKey, event.target.value)}
          inputProps={{ min: 0, max, step }}
          sx={{ '& .MuiOutlinedInput-root': { height: 38 }, '& .MuiInputBase-input': { fontSize: '0.9rem' }, '& .MuiInputLabel-root': { fontSize: '0.86rem' } }}
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
          sx={{ '& .MuiOutlinedInput-root': { height: 38 }, '& .MuiInputBase-input': { fontSize: '0.9rem' }, '& .MuiInputLabel-root': { fontSize: '0.86rem' } }}
          InputProps={{ endAdornment: unit ? <InputAdornment position="end">{unit}</InputAdornment> : undefined }}
        />
      </Stack>
    </FilterPopoverPaper>
  );
};

const MaturityEditor: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const [mode, setMode] = useState<'period' | 'presets'>('period');
  const presets = [
    { label: 'До 1 года', from: asInputDate(new Date()), to: datePlusYears(1) },
    { label: '1–3 года', from: datePlusYears(1), to: datePlusYears(3) },
    { label: '3–5 лет', from: datePlusYears(3), to: datePlusYears(5) },
    { label: 'Более 5 лет', from: datePlusYears(5), to: null },
  ];

  return (
    <FilterPopoverPaper title="Дата погашения" width={360}>
      <Stack direction="row" spacing={0.5} sx={{ mb: 1 }}>
        <Button size="small" variant={mode === 'period' ? 'contained' : 'text'} onClick={() => setMode('period')} sx={{ minHeight: 34, px: 0.75, borderRadius: 2, fontSize: '0.86rem' }}>
          Период
        </Button>
        <Button size="small" variant={mode === 'presets' ? 'contained' : 'text'} onClick={() => setMode('presets')} sx={{ minHeight: 34, px: 0.75, borderRadius: 2, fontSize: '0.86rem' }}>
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
            sx={{ '& .MuiOutlinedInput-root': { height: 38 }, '& .MuiInputBase-input': { fontSize: '0.88rem', px: 1 } }}
          />
          <TextField
            label="По"
            type="date"
            size="small"
            fullWidth
            value={draftFilters.matdateTo || ''}
            onChange={(event) => setDraftFilter('matdateTo', event.target.value || null)}
            InputLabelProps={{ shrink: true }}
            sx={{ '& .MuiOutlinedInput-root': { height: 38 }, '& .MuiInputBase-input': { fontSize: '0.88rem', px: 1 } }}
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
              sx={{ minHeight: 34, px: 0.85, borderRadius: 2, textTransform: 'none', fontSize: '0.84rem' }}
            >
              {preset.label}
            </Button>
          ))}
        </Stack>
      )}
    </FilterPopoverPaper>
  );
};

const RatingEditor: React.FC = () => {
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
        <Typography sx={{ mb: 0.45, fontSize: '0.84rem', fontWeight: 600, color: '#637A98' }}>{label}</Typography>
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
            minHeight: 40,
            justifyContent: 'space-between',
            px: 1.1,
            borderColor: isOpen ? '#287AF3' : 'rgba(134,164,205,0.4)',
            borderRadius: '10px',
            bgcolor: 'rgba(255,255,255,0.86)',
            color: '#253C5E',
            fontSize: '0.88rem',
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
              maxHeight: 168,
              overflowY: 'auto',
              overscrollBehavior: 'contain',
              border: '1px solid rgba(134,164,205,0.28)',
              borderRadius: '10px',
              bgcolor: '#fff',
              boxShadow: '0 6px 16px rgba(40,70,120,0.10)',
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
                    minHeight: 30,
                    px: 0.8,
                    border: 0,
                    bgcolor: selected ? 'rgba(40,122,243,0.10)' : 'transparent',
                    color: selected ? '#075DD1' : '#253C5E',
                    textAlign: 'left',
                    font: 'inherit',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    '&:hover, &:focus-visible': { bgcolor: 'rgba(40,122,243,0.08)', outline: 'none' },
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
    <FilterPopoverPaper title="Кредитный рейтинг" width={270}>
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

const CheckboxListEditor: React.FC<{
  title: string;
  options: FilterOption[];
  selected: Array<string | number>;
  onToggle: (value: string | number) => void;
}> = ({ title, options, selected, onToggle }) => (
  <FilterPopoverPaper title={title} width={title === 'Уровень листинга' ? 220 : title === 'Валюта' ? 230 : title === 'Тип облигации' ? 260 : title === 'Вид облигации' ? 285 : 260}>
    <Box sx={{
      display: 'grid',
      gridTemplateColumns: title === 'Месяц выплаты' ? 'repeat(2, minmax(0, 1fr))' : '1fr',
      columnGap: title === 'Месяц выплаты' ? 1 : 0,
      maxHeight: 230,
      overflowY: 'auto',
      mx: -0.5,
    }}>
      {options.map((option) => (
        <FormControlLabel
          key={option.value}
          control={<Checkbox size="small" checked={selected.includes(option.value)} onChange={() => onToggle(option.value)} sx={{ p: 0.35, mr: 0.4 }} />}
          label={option.label}
          sx={{ display: 'flex', mx: 0, my: 0, minHeight: 30, '& .MuiFormControlLabel-label': { fontSize: '0.86rem', lineHeight: 1.35, color: '#253C5E' } }}
        />
      ))}
    </Box>
  </FilterPopoverPaper>
);

const BondMarketFilters: React.FC = () => {
  const { filters, draftFilters, setDraftFilter, applyFilters, resetFilters } = useFiltersStore();
  const [openFilter, setOpenFilter] = useState<{ id: FilterId; anchor: HTMLElement } | null>(null);

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

  const toggleFilter = useCallback((id: FilterId, anchor: HTMLElement) => {
    setOpenFilter((current) => current?.id === id ? null : { id, anchor });
  }, []);

  const closeAllPopovers = useCallback(() => setOpenFilter(null), []);
  const handleClickAway = useCallback((event: MouseEvent | TouchEvent) => {
    const target = event.target;
    if (target instanceof Element && target.closest('.MuiMenu-root, .MuiPopover-root')) return;
    closeAllPopovers();
  }, [closeAllPopovers]);

  useEffect(() => {
    if (!openFilter) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeAllPopovers();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closeAllPopovers, openFilter]);

  const handleReset = useCallback(() => {
    resetFilters();
    closeAllPopovers();
  }, [closeAllPopovers, resetFilters]);

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

    if (draftFilters.matdateFrom || draftFilters.matdateTo) {
      const from = draftFilters.matdateFrom ? displayDate(draftFilters.matdateFrom) : 'любая дата';
      const to = draftFilters.matdateTo ? displayDate(draftFilters.matdateTo) : 'без ограничения';
      result.push({ key: 'maturity', label: `Погашение: ${from} — ${to}`, onDelete: () => clearFilter('maturity') });
    }
    addRangeChip('yield', 'Доходность', draftFilters.yieldMin, draftFilters.yieldMax);
    addRangeChip('coupon', 'Купон', draftFilters.couponMin, draftFilters.couponMax);
    addRangeChip('couponYield', 'Купон к цене', draftFilters.couponYieldMin, draftFilters.couponYieldMax);
    if (draftFilters.ratingMin || draftFilters.ratingMax) {
      result.push({
        key: 'rating',
        label: `Рейтинг: ${draftFilters.ratingMin ?? 'любой'} — ${draftFilters.ratingMax ?? 'любой'}`,
        onDelete: () => clearFilter('rating'),
      });
    }

    const groupLabels: Array<[Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, string]> = [
      ['couponMonths', 'Месяцы купона'], ['currency', 'Валюта'], ['bondType', 'Тип'], ['bondKind', 'Вид'], ['listing', 'Листинг'],
    ];
    groupLabels.forEach(([id, title]) => {
      const labels = labelsFor(id);
      if (labels.length > 0) result.push({ key: id, label: `${title}: ${compactLabels(labels)}`, onDelete: () => clearFilter(id) });
    });
    return result;
  }, [clearFilter, draftFilters, selectedFor]);

  const renderPopoverContent = (id: FilterId) => {
    switch (id) {
      case 'maturity': return <MaturityEditor />;
      case 'yield': return <NumericRangeEditor title="Доходность к погашению" minKey="yieldMin" maxKey="yieldMax" max={30} step={0.1} />;
      case 'coupon': return <NumericRangeEditor title="Ставка купона" minKey="couponMin" maxKey="couponMax" max={30} step={0.5} />;
      case 'couponYield': return <NumericRangeEditor title="Купонная доходность к текущей цене" minKey="couponYieldMin" maxKey="couponYieldMax" max={100} step={0.1} />;
      case 'rating': return <RatingEditor />;
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
            onToggle={(value) => toggleArrayValue(id as Extract<FilterId, 'couponMonths' | 'currency' | 'bondType' | 'bondKind' | 'listing'>, value)}
          />
        );
      default: return null;
    }
  };

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
          p: { xs: 0.9, sm: 1.1, md: 1.25 },
          border: '1px solid rgba(255,255,255,0.9)',
          borderRadius: { xs: '18px', md: '24px' },
          background: 'linear-gradient(118deg, rgba(255,255,255,0.78) 0%, rgba(237,245,255,0.72) 55%, rgba(219,234,255,0.68) 100%)',
          boxShadow: '0 12px 32px rgba(61, 99, 160, 0.10), inset 0 1px 0 rgba(255,255,255,0.9)',
          backdropFilter: 'blur(20px) saturate(145%)',
        }}
      >
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: { xs: 0.55, md: 0.7 },
        pr: isDirty ? '70px' : 0,
      }}>
        <TextField
          size="small"
          placeholder="Поиск по коду, названию или ISIN"
          value={draftFilters.search}
          onChange={(event) => setDraftFilter('search', event.target.value)}
          sx={{
            flex: '1 1 230px',
            maxWidth: { md: 320 },
            '& .MuiOutlinedInput-root': { height: 40, borderRadius: '10px', bgcolor: 'rgba(255,255,255,0.76)' },
            '& .MuiInputBase-input': { fontSize: '0.88rem' },
          }}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon sx={{ color: '#152F57', fontSize: 18 }} /></InputAdornment>,
            endAdornment: draftFilters.search ? (
              <InputAdornment position="end">
                <IconButton size="small" aria-label="Очистить поиск" onClick={() => setDraftFilter('search', '')} edge="end">
                  <CloseIcon sx={{ fontSize: 15 }} />
                </IconButton>
              </InputAdornment>
            ) : undefined,
          }}
          inputProps={{ 'aria-label': 'Поиск по коду, названию или ISIN' }}
        />

        {FILTER_BUTTONS.map((filter) => {
          const isOpen = openFilter?.id === filter.id;
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
              sx={{
                minHeight: 34,
                px: { xs: 0.75, sm: 0.9 },
                borderRadius: '10px',
                borderColor: isOpen ? '#287AF3' : 'rgba(134,164,205,0.28)',
                bgcolor: isOpen ? 'rgba(225,239,255,0.95)' : 'rgba(255,255,255,0.76)',
                color: isOpen ? '#075DD1' : '#18345D',
                fontSize: '0.84rem',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                boxShadow: isOpen ? '0 0 0 2px rgba(40,122,243,0.12)' : '0 2px 5px rgba(64,98,149,0.04)',
                '&:hover': { borderColor: '#5A9BFA', bgcolor: 'rgba(239,246,255,0.96)' },
                '& .MuiButton-startIcon': { mr: 0.55, '& svg': { fontSize: 16 } },
                '& .MuiButton-endIcon': { ml: 0.35, '& svg': { fontSize: 15 } },
              }}
            >
              {filter.label}
            </Button>
          );
        })}
      </Box>

      {isDirty && (
        <Box sx={{
          position: 'absolute',
          top: { xs: 8, sm: 10, md: 11 },
          right: { xs: 8, sm: 10, md: 11 },
          display: 'flex',
          alignItems: 'center',
          gap: 0.25,
        }}>
          <IconButton
            size="small"
            disableRipple
            title="Применить фильтры"
            aria-label="Применить фильтры"
            disabled={invalidRanges}
            onClick={() => {
              applyFilters();
              closeAllPopovers();
            }}
            sx={{
              width: 30,
              height: 34,
              p: 0,
              borderRadius: 0,
              color: '#16864B',
              bgcolor: 'transparent',
              '&:hover': { bgcolor: 'transparent', '& svg': { transform: 'scale(1.08)' } },
              '&:focus-visible': { outline: '2px solid rgba(22,134,75,0.45)', outlineOffset: 1 },
              '&:disabled': { color: 'rgba(22,134,75,0.35)' },
              '& svg': { transition: 'transform 120ms ease' },
            }}
          >
            <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="23" height="23" fill="none">
              <path d="M4.5 12.5 9.4 17.2 19.5 6.8" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </IconButton>
          <IconButton
            size="small"
            disableRipple
            title="Сбросить фильтры"
            aria-label="Сбросить фильтры"
            onClick={handleReset}
            sx={{
              width: 30,
              height: 34,
              p: 0,
              borderRadius: 0,
              color: '#C63D45',
              bgcolor: 'transparent',
              '&:hover': { bgcolor: 'transparent', '& svg': { transform: 'scale(1.08)' } },
              '&:focus-visible': { outline: '2px solid rgba(198,61,69,0.4)', outlineOffset: 1 },
              '& svg': { transition: 'transform 120ms ease' },
            }}
          >
            <ClearFiltersSvg />
          </IconButton>
        </Box>
      )}

      {chips.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.8 }}>
          {chips.map((chip) => (
            <Chip
              key={chip.key}
              label={chip.label}
              size="small"
              onDelete={chip.onDelete}
              deleteIcon={<CloseIcon />}
              sx={{
                height: 26,
                pl: 0.25,
                border: '1px solid rgba(67,139,235,0.22)',
                bgcolor: 'rgba(194,222,255,0.76)',
                color: '#0759C7',
                fontSize: '0.82rem',
                fontWeight: 500,
                '& .MuiChip-deleteIcon': { color: '#1769D5', fontSize: 16, '&:hover': { color: '#0A4DAA' } },
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
                width: 30,
                height: 26,
                p: 0,
                ml: 'auto',
                borderRadius: 0,
                color: '#C63D45',
                bgcolor: 'transparent',
                '&:hover': { bgcolor: 'transparent', '& svg': { transform: 'scale(1.08)' } },
                '&:focus-visible': { outline: '2px solid rgba(198,61,69,0.4)', outlineOffset: 1 },
                '& svg': { transition: 'transform 120ms ease' },
              }}
            >
              <ClearFiltersSvg />
            </IconButton>
          )}
        </Box>
      )}

      {invalidRanges && (
        <Typography role="alert" sx={{ mt: 0.6, fontSize: '0.8rem', color: '#C62828' }}>
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
            <Box sx={{ mt: 0.5, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.94)', borderRadius: '15px', bgcolor: 'rgba(255,255,255,0.96)', boxShadow: '0 12px 30px rgba(40,70,120,0.17)', backdropFilter: 'blur(22px)' }}>
              <Box id={`bond-filter-popover-${id}`} role="dialog" aria-label={filter.label} data-bond-filter-popover="true">
                {renderPopoverContent(id)}
              </Box>
            </Box>
          </Popper>
        );
      })()}
      </Box>
    </ClickAwayListener>
  );
};

export default BondMarketFilters;
