import React from 'react';
import {
  Box,
  TextField,
  Typography,
  Slider,
  Chip,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
  Stack,
  alpha,
  CircularProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { keyframes } from '@emotion/react';
import SearchIcon from '@mui/icons-material/Search';
import { useFiltersStore } from '../../stores/filtersStore';

// ============================================================================
// Константы
// ============================================================================

const MIN_COUPON = 0;
const MAX_COUPON = 30;
const COUPON_STEP = 0.5;

const MIN_YIELD = 0;
const MAX_YIELD = 30;
const YIELD_STEP = 0.5;

const MAX_COUPON_YIELD = 100;

const RATINGS = [
  'AAA',
  'AA+', 'AA', 'AA-',
  'A+', 'A', 'A-',
  'BBB+', 'BBB', 'BBB-',
  'BB+', 'BB', 'BB-',
  'B+', 'B', 'B-',
  'CCC+', 'CCC', 'CCC-',
  'CC', 'C',
  'D'
];

const BOND_TYPE43_OPTIONS = [
  'Амортизируемые облигации',
  'Валютные облигации',
  'Конвертируемые облигации',
  'Линкер/облигации с индексируемым',
  'Структурная облигация',
  'Фикс с известным купоном',
  'Фикс с неизвестным купоном',
  'Флоатер',
];

const BOND_TYPE_LABELS: Record<string, string> = {
  "exchange_bond": "Биржевая облигация",
  "ofz_bond": "ОФЗ (Государственная облигация)",
  "corporate_bond": "Корпоративная облигация",
  "municipal_bond": "Муниципальная облигация",
  "subfederal_bond": "Региональная облигация",
};

// ============================================================================
// Общие стили для TextField (премиум стиль)
// ============================================================================

const premiumTextFieldStyles = {
  borderRadius: '12px',
  '& .MuiOutlinedInput-root': {
    borderRadius: '12px',
    backgroundColor: 'grey.50',
    fontWeight: 500,
    '& fieldset': {
      borderWidth: '1px',
      borderColor: 'grey.300',
    },
    '&:hover fieldset': {
      borderColor: 'grey.400',
    },
    '&.Mui-focused': {
      backgroundColor: 'background.paper',
      boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.08)',
      '& fieldset': {
        borderWidth: '1px',
        borderColor: 'primary.main',
      },
    },
  },
  '& .MuiInputBase-input': {
    fontWeight: 500,
  },
};

// ============================================================================
// Функция для создания стилей премиум слайдера
// ============================================================================

const getPremiumSliderStyles = (theme: any, color: 'primary' | 'success' | 'warning' | 'error') => {
  const colorValue = theme.palette[color].main;
  
  // Создаем keyframes для пульсации фокуса с динамическим цветом
  const pulseKeyframes = keyframes`
    0% {
      box-shadow: 0 0 0 0 ${alpha(colorValue, 0.4)};
    }
    70% {
      box-shadow: 0 0 0 8px ${alpha(colorValue, 0)};
    }
    100% {
      box-shadow: 0 0 0 0 ${alpha(colorValue, 0)};
    }
  `;
  
  return {
    height: 6,
    '& .MuiSlider-thumb': {
      width: 20,
      height: 20,
      backgroundColor: 'white',
      border: `2px solid ${colorValue}`,
      boxShadow: '0px 2px 4px rgba(0,0,0,0.2)',
      '&::before': {
        boxShadow: 'none',
      },
      // Базовое состояние
      '&:hover': {
        boxShadow: `0px 4px 12px ${alpha(colorValue, 0.4)}`,
        transition: 'box-shadow 0.2s ease',
      },
      '&.Mui-focusVisible': {
        boxShadow: `0px 4px 12px ${alpha(colorValue, 0.4)}`,
        transition: 'box-shadow 0.2s ease',
        // Пульсация для фокуса
        animation: `${pulseKeyframes} 1.5s infinite`,
      },
      '&.Mui-active': {
        boxShadow: `0px 6px 16px ${alpha(colorValue, 0.5)}`,
        transition: 'box-shadow 0.2s ease',
      },
    },
    '& .MuiSlider-track': {
      height: 6,
      borderRadius: '3px',
      border: 'none',
    },
    '& .MuiSlider-rail': {
      height: 6,
      borderRadius: '3px',
      opacity: 0.3,
    },
    '& .MuiSlider-valueLabel': {
      fontSize: '0.75rem',
      padding: '4px 8px',
      borderRadius: '8px',
      fontWeight: 600,
    },
  };
};

// ============================================================================
// 1. Поиск (SearchFilter)
// ============================================================================

export const SearchFilter: React.FC = () => {
  const { filters, setFilter } = useFiltersStore();

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFilter('search', event.target.value);
  };

  return (
    <TextField
      size="small"
      placeholder="Поиск по коду, названию или ISIN"
      value={filters.search}
      onChange={handleChange}
      fullWidth
      sx={premiumTextFieldStyles}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon />
          </InputAdornment>
        ),
      }}
    />
  );
};

// ============================================================================
// 2. Доходность купона относительно номинала (CouponRangeFilter)
// ============================================================================

export const CouponRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const theme = useTheme();

  const minCoupon = draftFilters.couponMin ?? MIN_COUPON;
  const maxCoupon = draftFilters.couponMax ?? MAX_COUPON;

  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('couponMin', min === MIN_COUPON ? null : min);
      setDraftFilter('couponMax', max === MAX_COUPON ? null : max);
    }
  };

  return (
    <Stack spacing={2} sx={{ width: '100%' }}>
      {/* Визуальные боксы значений */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, width: '100%' }}>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ОТ
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {minCoupon.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ДО
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {maxCoupon.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Премиум слайдер */}
      <Box sx={{ px: 1 }}>
        <Slider
          value={[minCoupon, maxCoupon]}
          onChange={handleSliderChange}
          min={MIN_COUPON}
          max={MAX_COUPON}
          step={COUPON_STEP}
          marks={false}
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => `${value}%`}
          sx={getPremiumSliderStyles(theme, 'primary')}
        />
      </Box>
    </Stack>
  );
};

// ============================================================================
// 3. Доходность к погашению (YieldRangeFilter)
// ============================================================================

export const YieldRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const theme = useTheme();

  const minYield = draftFilters.yieldMin ?? MIN_YIELD;
  const maxYield = draftFilters.yieldMax ?? MAX_YIELD;

  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('yieldMin', min === MIN_YIELD ? null : min);
      setDraftFilter('yieldMax', max === MAX_YIELD ? null : max);
    }
  };

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ОТ
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {minYield.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ДО
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {maxYield.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ px: 1 }}>
        <Slider
          value={[minYield, maxYield]}
          onChange={handleSliderChange}
          min={MIN_YIELD}
          max={MAX_YIELD}
          step={YIELD_STEP}
          marks={false}
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => `${value}%`}
          color="primary"
          sx={getPremiumSliderStyles(theme, 'primary')}
        />
      </Box>
    </Stack>
  );
};

// ============================================================================
// 4. Доходность купона к текущей цене (CouponYieldRangeFilter)
// ============================================================================

export const CouponYieldRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const theme = useTheme();

  const minValue = draftFilters.couponYieldMin ?? 0;
  const maxValue = draftFilters.couponYieldMax ?? MAX_COUPON_YIELD;

  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('couponYieldMin', min);
      setDraftFilter('couponYieldMax', max);
    }
  };

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ОТ
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {minValue.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ДО
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {maxValue.toFixed(1)}%
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ px: 1 }}>
        <Slider
          value={[minValue, maxValue]}
          onChange={handleSliderChange}
          min={0}
          max={MAX_COUPON_YIELD}
          step={0.1}
          marks={false}
          valueLabelDisplay="off"
          color="primary"
          sx={getPremiumSliderStyles(theme, 'primary')}
        />
      </Box>
    </Stack>
  );
};

// ============================================================================
// 5. Дата погашения (MaturityDateFilter)
// ============================================================================

export const MaturityDateFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const handleFromChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setDraftFilter('matdateFrom', event.target.value || null);
  };

  const handleToChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setDraftFilter('matdateTo', event.target.value || null);
  };

  return (
    <Stack direction="row" spacing={2} sx={{ width: '100%' }}>
      <TextField
        size="small"
        type="date"
        label="От"
        value={draftFilters.matdateFrom || ''}
        onChange={handleFromChange}
        InputLabelProps={{ shrink: true }}
        sx={{ flex: 1, ...premiumTextFieldStyles }}
      />
      <TextField
        size="small"
        type="date"
        label="До"
        value={draftFilters.matdateTo || ''}
        onChange={handleToChange}
        InputLabelProps={{ shrink: true }}
        sx={{ flex: 1, ...premiumTextFieldStyles }}
      />
    </Stack>
  );
};

// ============================================================================
// 6. Уровень листинга (ListLevelFilter) - Chip вместо Checkbox
// ============================================================================

export const ListLevelFilter: React.FC = () => {
  const { draftFilters, setDraftFilter, filterOptions, isLoadingFilterOptions } = useFiltersStore();

  const handleToggle = (value: number) => {
    const currentValues = draftFilters.listlevel || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('listlevel', newValues);
  };

  if (isLoadingFilterOptions || !filterOptions) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Загрузка...
        </Typography>
      </Box>
    );
  }

  const selectedValues = draftFilters.listlevel || [];
  const sortedLevels = [...(filterOptions.listlevels || [])].sort((a, b) => a - b);

  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ width: '100%' }}>
      {sortedLevels.map((level) => (
        <Chip
          key={level}
          label={`Уровень ${level}`}
          onClick={() => handleToggle(level)}
          color={selectedValues.includes(level) ? 'primary' : 'default'}
          variant={selectedValues.includes(level) ? 'filled' : 'outlined'}
          sx={{
            fontWeight: selectedValues.includes(level) ? 600 : 400,
            cursor: 'pointer',
            '&:hover': {
              transform: 'scale(1.05)',
              transition: 'transform 0.2s',
            },
          }}
        />
      ))}
    </Stack>
  );
};

// ============================================================================
// 7. Валюта (CurrencyFilter) - Chip вместо Autocomplete
// ============================================================================

export const CurrencyFilter: React.FC = () => {
  const { draftFilters, setDraftFilter, filterOptions, isLoadingFilterOptions } = useFiltersStore();

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.faceunit || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('faceunit', newValues);
  };

  if (isLoadingFilterOptions || !filterOptions) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Загрузка...
        </Typography>
      </Box>
    );
  }

  const selectedValues = draftFilters.faceunit || [];

  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ width: '100%' }}>
      {(filterOptions.faceunits || []).map((currency) => (
        <Chip
          key={currency}
          label={currency}
          onClick={() => handleToggle(currency)}
          color={selectedValues.includes(currency) ? 'primary' : 'default'}
          variant={selectedValues.includes(currency) ? 'filled' : 'outlined'}
          sx={{
            fontWeight: selectedValues.includes(currency) ? 600 : 400,
            cursor: 'pointer',
            '&:hover': {
              transform: 'scale(1.05)',
              transition: 'transform 0.2s',
            },
          }}
        />
      ))}
    </Stack>
  );
};

// ============================================================================
// 8. Тип облигации (BondTypeFilter) - Chip вместо Checkbox
// ============================================================================

export const BondTypeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter, filterOptions, isLoadingFilterOptions } = useFiltersStore();

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.bondtype || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('bondtype', newValues);
  };

  if (isLoadingFilterOptions || !filterOptions) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Загрузка...
        </Typography>
      </Box>
    );
  }

  const availableBondTypes = (filterOptions.bondtypes || []).filter(
    type => type in BOND_TYPE_LABELS
  );

  const selectedValues = draftFilters.bondtype || [];

  return (
    <Stack direction="column" spacing={1} sx={{ width: '100%' }}>
      {availableBondTypes.map((type) => (
        <Chip
          key={type}
          label={BOND_TYPE_LABELS[type] || type}
          onClick={() => handleToggle(type)}
          color={selectedValues.includes(type) ? 'primary' : 'default'}
          variant={selectedValues.includes(type) ? 'filled' : 'outlined'}
          sx={{
            width: 'fit-content',
            fontWeight: selectedValues.includes(type) ? 600 : 400,
            cursor: 'pointer',
            '&:hover': {
              transform: 'scale(1.02)',
              transition: 'transform 0.2s',
            },
          }}
        />
      ))}
    </Stack>
  );
};

// ============================================================================
// 9. Вид облигации (BondType43Filter) - Chip вместо Checkbox
// ============================================================================

export const BondType43Filter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.bondtype43 || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('bondtype43', newValues);
  };

  const selectedValues = draftFilters.bondtype43 || [];

  return (
    <Stack direction="column" spacing={1} sx={{ width: '100%' }}>
      {BOND_TYPE43_OPTIONS.map((option) => (
        <Chip
          key={option}
          label={option}
          onClick={() => handleToggle(option)}
          color={selectedValues.includes(option) ? 'primary' : 'default'}
          variant={selectedValues.includes(option) ? 'filled' : 'outlined'}
          sx={{
            width: 'fit-content',
            fontWeight: selectedValues.includes(option) ? 600 : 400,
            cursor: 'pointer',
            '&:hover': {
              transform: 'scale(1.02)',
              transition: 'transform 0.2s',
            },
          }}
        />
      ))}
    </Stack>
  );
};

// ============================================================================
// 10. Рейтинг (RatingRangeFilter)
// ============================================================================

export const RatingRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();
  const theme = useTheme();

  const minRatingIndex = draftFilters.ratingMin !== null 
    ? RATINGS.indexOf(draftFilters.ratingMin) 
    : 0;
  const maxRatingIndex = draftFilters.ratingMax !== null 
    ? RATINGS.indexOf(draftFilters.ratingMax) 
    : RATINGS.length - 1;

  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [minIndex, maxIndex] = newValue;
      setDraftFilter('ratingMin', RATINGS[minIndex]);
      setDraftFilter('ratingMax', RATINGS[maxIndex]);
    }
  };

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ОТ
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {RATINGS[minRatingIndex]}
            </Typography>
          </Box>
        </Box>
        <Box
          sx={{
            flex: 1,
            px: 2,
            py: 0.75,
            borderRadius: '12px',
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography component="span" color="text.secondary" sx={{ fontSize: '0.875rem', mr: '1rem' }}>
              ДО
            </Typography>
            <Typography component="span" fontWeight={700} color="primary.main" sx={{ fontSize: '1.5rem' }}>
              {RATINGS[maxRatingIndex]}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ px: 1 }}>
        <Slider
          value={[minRatingIndex, maxRatingIndex]}
          onChange={handleSliderChange}
          min={0}
          max={RATINGS.length - 1}
          step={1}
          marks={false}
          valueLabelDisplay="off"
          color="primary"
          sx={getPremiumSliderStyles(theme, 'primary')}
        />
      </Box>
    </Stack>
  );
};
