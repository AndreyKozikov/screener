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
        backgroundColor: 'white',
        '& .MuiOutlinedInput-root': {
          backgroundColor: 'white',
          color: 'black',
          '& fieldset': {
            borderColor: 'rgba(0, 0, 0, 0.23)',
          },
          '&:hover fieldset': {
            borderColor: 'rgba(0, 0, 0, 0.87)',
          },
          '&.Mui-focused fieldset': {
            borderColor: 'primary.main',
          },
        },
        '& .MuiInputBase-input': {
          color: 'black',
          '&::placeholder': {
            color: 'rgba(0, 0, 0, 0.6)',
            fontSize: '0.75rem',
            opacity: 1,
          },
        },
        '& .MuiInputAdornment-root': {
          color: 'rgba(0, 0, 0, 0.54)',
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
