import React from 'react';
import { Box, TextField, Typography, Slider } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

// Yield to maturity range constants
const MIN_YIELD = 0;
const MAX_YIELD = 30;
const YIELD_STEP = 0.5;

/**
 * YieldRangeFilter Component
 * 
 * Dual slider for filtering bonds by yield to maturity range
 * Allows selection from minimum to maximum yield percentage
 */
export const YieldRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  // Get current yield values (default to full range)
  const minYield = draftFilters.yieldMin ?? MIN_YIELD;
  const maxYield = draftFilters.yieldMax ?? MAX_YIELD;

  // Handle slider change
  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [min, max] = newValue;
      setDraftFilter('yieldMin', min === MIN_YIELD ? null : min);
      setDraftFilter('yieldMax', max === MAX_YIELD ? null : max);
    }
  };

  // Handle min yield text input change
  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    if (value === null || (value >= MIN_YIELD && value <= MAX_YIELD)) {
      setDraftFilter('yieldMin', value);
    }
  };

  // Handle max yield text input change
  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    if (value === null || (value >= MIN_YIELD && value <= MAX_YIELD)) {
      setDraftFilter('yieldMax', value);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Text inputs for min and max yield */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          size="small"
          type="number"
          placeholder="От"
          value={draftFilters.yieldMin ?? ''}
          onChange={handleMinChange}
          inputProps={{
            min: MIN_YIELD,
            max: MAX_YIELD,
            step: YIELD_STEP,
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
          value={draftFilters.yieldMax ?? ''}
          onChange={handleMaxChange}
          inputProps={{
            min: MIN_YIELD,
            max: MAX_YIELD,
            step: YIELD_STEP,
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
          value={[minYield, maxYield]}
          onChange={handleSliderChange}
          min={MIN_YIELD}
          max={MAX_YIELD}
          step={YIELD_STEP}
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

      {/* Display current yield range below slider */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {minYield.toFixed(1)}%
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {maxYield.toFixed(1)}%
        </Typography>
      </Box>
    </Box>
  );
};

export default YieldRangeFilter;
