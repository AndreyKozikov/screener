import React from 'react';
import { Box, TextField, Typography } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * CouponRangeFilter Component
 * 
 * Number inputs for filtering bonds by coupon rate range
 */
export const CouponRangeFilter: React.FC = () => {
  const { filters, setFilter } = useFiltersStore();

  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    setFilter('couponMin', value);
  };

  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value === '' ? null : parseFloat(event.target.value);
    setFilter('couponMax', value);
  };

  return (
    <Box>
      <Typography variant="body2" gutterBottom color="text.secondary" fontWeight={500}>
        Купон, %
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          size="small"
          type="number"
          placeholder="От"
          value={filters.couponMin ?? ''}
          onChange={handleMinChange}
          inputProps={{
            min: 0,
            max: 100,
            step: 0.1,
          }}
          sx={{ flex: 1 }}
        />
        <Typography variant="body2" color="text.secondary">
          —
        </Typography>
        <TextField
          size="small"
          type="number"
          placeholder="До"
          value={filters.couponMax ?? ''}
          onChange={handleMaxChange}
          inputProps={{
            min: 0,
            max: 100,
            step: 0.1,
          }}
          sx={{ flex: 1 }}
        />
      </Box>
    </Box>
  );
};

export default CouponRangeFilter;
