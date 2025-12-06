import React from 'react';
import { Box, TextField, Typography, Slider } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * Rating scale - from highest to lowest
 */
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

/**
 * RatingRangeFilter Component
 * 
 * Dual slider for filtering bonds by rating range
 * Allows selection from minimum to maximum rating
 */
export const RatingRangeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  // Get current rating indices (default to full range)
  const minRatingIndex = draftFilters.ratingMin !== null 
    ? RATINGS.indexOf(draftFilters.ratingMin) 
    : 0;
  const maxRatingIndex = draftFilters.ratingMax !== null 
    ? RATINGS.indexOf(draftFilters.ratingMax) 
    : RATINGS.length - 1;

  // Handle slider change
  const handleSliderChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const [minIndex, maxIndex] = newValue;
      setDraftFilter('ratingMin', RATINGS[minIndex]);
      setDraftFilter('ratingMax', RATINGS[maxIndex]);
    }
  };

  // Handle min rating text input change
  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value.trim().toUpperCase();
    if (value === '') {
      setDraftFilter('ratingMin', null);
    } else if (RATINGS.includes(value)) {
      setDraftFilter('ratingMin', value);
    }
  };

  // Handle max rating text input change
  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value.trim().toUpperCase();
    if (value === '') {
      setDraftFilter('ratingMax', null);
    } else if (RATINGS.includes(value)) {
      setDraftFilter('ratingMax', value);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Text inputs for min and max rating */}
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          size="small"
          placeholder="От"
          value={draftFilters.ratingMin ?? ''}
          onChange={handleMinChange}
          inputProps={{
            style: { textAlign: 'center', textTransform: 'uppercase' }
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
          placeholder="До"
          value={draftFilters.ratingMax ?? ''}
          onChange={handleMaxChange}
          inputProps={{
            style: { textAlign: 'center', textTransform: 'uppercase' }
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
          value={[minRatingIndex, maxRatingIndex]}
          onChange={handleSliderChange}
          min={0}
          max={RATINGS.length - 1}
          step={1}
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

      {/* Display current rating range below slider */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {RATINGS[minRatingIndex]}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {RATINGS[maxRatingIndex]}
        </Typography>
      </Box>
    </Box>
  );
};

export default RatingRangeFilter;

