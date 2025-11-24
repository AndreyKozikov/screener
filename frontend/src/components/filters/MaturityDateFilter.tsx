import React from 'react';
import { Box, TextField, Typography } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * MaturityDateFilter Component
 * 
 * Date inputs for filtering bonds by maturity date range
 */
export const MaturityDateFilter: React.FC = () => {
  const { filters, setFilter } = useFiltersStore();

  const handleFromChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFilter('matdateFrom', event.target.value || null);
  };

  const handleToChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFilter('matdateTo', event.target.value || null);
  };

  return (
    <Box>
      <Typography variant="body2" gutterBottom color="text.secondary" fontWeight={500}>
        Дата погашения
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <TextField
          size="small"
          type="date"
          label="От"
          value={filters.matdateFrom || ''}
          onChange={handleFromChange}
          InputLabelProps={{
            shrink: true,
          }}
        />
        <TextField
          size="small"
          type="date"
          label="До"
          value={filters.matdateTo || ''}
          onChange={handleToChange}
          InputLabelProps={{
            shrink: true,
          }}
        />
      </Box>
    </Box>
  );
};

export default MaturityDateFilter;
