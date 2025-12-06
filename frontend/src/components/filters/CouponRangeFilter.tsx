import React from 'react';
import { Box, TextField, Typography, Slider } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

// Coupon percentage range constants
const MIN_COUPON = 0;
const MAX_COUPON = 30;
const COUPON_STEP = 0.5;

/**
 * CouponRangeFilter Component
 * 
 * Dual slider for filtering bonds by coupon rate range (relative to face value)
 * Allows selection from minimum to maximum coupon percentage
 */
export const CouponRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  // Get current coupon values (default to full range)
  const minCoupon = draftFilters.couponMin ?? MIN_COUPON;
  const maxCoupon = draftFilters.couponMax ?? MAX_COUPON;

  // Handle slider change
  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('couponMin', min === MIN_COUPON ? null : min);
      setDraftFilter('couponMax', max === MAX_COUPON ? null : max);
    }
  };

  // Handle min coupon text input change
  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    if (value === null || (value >= MIN_COUPON && value <= MAX_COUPON)) {
      setDraftFilter('couponMin', value);
    }
  };

  // Handle max coupon text input change
  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    if (value === null || (value >= MIN_COUPON && value <= MAX_COUPON)) {
      setDraftFilter('couponMax', value);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Text inputs for min and max coupon */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          size="small"
          type="number"
          placeholder="От"
          value={draftFilters.couponMin ?? ''}
          onChange={handleMinChange}
          inputProps={{
            min: MIN_COUPON,
            max: MAX_COUPON,
            step: COUPON_STEP,
            style: { textAlign: 'center' }
          }}
          sx={{ 
            width: '80px',
            '& .MuiInputBase-input::placeholder': {
              fontSize: '0.75rem',
            },
          }}
        />
        <Typography variant="body2" color="text.secondary">
          —
        </Typography>
        <TextField
          size="small"
          type="number"
          placeholder="До"
          value={draftFilters.couponMax ?? ''}
          onChange={handleMaxChange}
          inputProps={{
            min: MIN_COUPON,
            max: MAX_COUPON,
            step: COUPON_STEP,
            style: { textAlign: 'center' }
          }}
          sx={{ 
            width: '80px',
            '& .MuiInputBase-input::placeholder': {
              fontSize: '0.75rem',
            },
          }}
        />
      </Box>

      {/* Dual slider */}
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
          size="small"
          sx={{
            height: 2,
            '& .MuiSlider-thumb': {
              width: 8,
              height: 8,
              '&:hover, &.Mui-focusVisible': {
                boxShadow: '0 0 0 4px rgba(25, 118, 210, 0.16)',
              },
            },
            '& .MuiSlider-track': {
              height: 2,
              border: 'none',
            },
            '& .MuiSlider-rail': {
              height: 2,
              opacity: 0.3,
            },
            '& .MuiSlider-valueLabel': {
              fontSize: '0.75rem',
              padding: '2px 6px',
            },
          }}
        />
      </Box>

      {/* Display current coupon range below slider */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {minCoupon.toFixed(1)}%
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {maxCoupon.toFixed(1)}%
        </Typography>
      </Box>
    </Box>
  );
};

export default CouponRangeFilter;
