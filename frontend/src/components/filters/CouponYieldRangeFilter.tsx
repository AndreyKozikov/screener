import React from 'react';
import { Box, TextField, Typography, Slider } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * CouponYieldRangeFilter Component
 * 
 * Dual slider for filtering bonds by coupon yield to price range
 * Min value: 0, Max value: 100
 */
export const CouponYieldRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  // Fixed range: 0 to 100
  const maxCouponYield = 100;

  // Get current values (default to full range)
  const minValue = draftFilters.couponYieldMin ?? 0;
  const maxValue = draftFilters.couponYieldMax ?? maxCouponYield;

  // Handle slider change
  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('couponYieldMin', min);
      setDraftFilter('couponYieldMax', max);
    }
  };

  // Handle min value text input change
  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    setDraftFilter('couponYieldMin', value);
  };

  // Handle max value text input change
  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    setDraftFilter('couponYieldMax', value);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Text inputs for min and max */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          size="small"
          type="number"
          placeholder="От"
          value={minValue}
          onChange={handleMinChange}
          inputProps={{
            min: 0,
            max: maxCouponYield,
            step: 0.1,
            style: { textAlign: 'center' }
          }}
          sx={{ 
            width: '80px',
            '& .MuiInputBase-root': {
              height: '32px',
            },
            '& .MuiInputBase-input': {
              padding: '4px 8px',
            },
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
          value={maxValue}
          onChange={handleMaxChange}
          inputProps={{
            min: 0,
            max: maxCouponYield,
            step: 0.1,
            style: { textAlign: 'center' }
          }}
          sx={{ 
            width: '80px',
            '& .MuiInputBase-root': {
              height: '32px',
            },
            '& .MuiInputBase-input': {
              padding: '4px 8px',
            },
            '& .MuiInputBase-input::placeholder': {
              fontSize: '0.75rem',
            },
          }}
        />
      </Box>

      {/* Dual slider */}
      <Box sx={{ px: 1 }}>
        <Slider
          value={[minValue, maxValue]}
          onChange={handleSliderChange}
          min={0}
          max={maxCouponYield}
          step={0.1}
          marks={false}
          valueLabelDisplay="off"
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
          }}
        />
      </Box>

      {/* Display current range below slider */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {minValue.toFixed(1)}%
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {maxValue.toFixed(1)}%
        </Typography>
      </Box>
    </Box>
  );
};

export default CouponYieldRangeFilter;

