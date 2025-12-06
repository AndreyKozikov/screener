import React from 'react';
import { Box, TextField, Typography } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * MaturityDateFilter Component
 * 
 * Date inputs for filtering bonds by maturity date range
 */
export const MaturityDateFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const handleFromChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setDraftFilter('matdateFrom', event.target.value || null);
  };

  const handleToChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setDraftFilter('matdateTo', event.target.value || null);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', gap: 1, alignItems: 'center' }}>
      <TextField
        size="small"
        type="date"
        label="Дата погашения От"
        value={draftFilters.matdateFrom || ''}
        onChange={handleFromChange}
        InputLabelProps={{
          shrink: true,
        }}
        sx={{
          width: '33.33%',
          '& .MuiInputBase-root': {
            height: '32px',
          },
          '& .MuiInputBase-input': {
            padding: '4px 8px',
          },
          '& input[type="date"]::-webkit-calendar-picker-indicator': {
            cursor: 'pointer',
          },
          '& .MuiInputLabel-root': {
            fontSize: '0.75rem',
          },
        }}
      />
      <TextField
        size="small"
        type="date"
        label="Дата погашения До"
        value={draftFilters.matdateTo || ''}
        onChange={handleToChange}
        InputLabelProps={{
          shrink: true,
        }}
        sx={{
          width: '33.33%',
          '& .MuiInputBase-root': {
            height: '32px',
          },
          '& .MuiInputBase-input': {
            padding: '4px 8px',
          },
          '& input[type="date"]::-webkit-calendar-picker-indicator': {
            cursor: 'pointer',
          },
          '& .MuiInputLabel-root': {
            fontSize: '0.75rem',
          },
        }}
      />
    </Box>
  );
};

export default MaturityDateFilter;
