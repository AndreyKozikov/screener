import React from 'react';
import { TextField, InputAdornment } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * SearchFilter Component
 * 
 * Text input for searching bonds by SECID or SHORTNAME
 */
export const SearchFilter: React.FC = () => {
  const { filters, setFilter } = useFiltersStore();

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFilter('search', event.target.value);
  };

  return (
    <TextField
      size="small"
      placeholder="Поиск по коду или названию"
      value={filters.search}
      onChange={handleChange}
      sx={{ 
        width: '100%',
        '& .MuiInputBase-input::placeholder': {
          fontSize: '0.75rem',
        },
      }}
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

export default SearchFilter;
