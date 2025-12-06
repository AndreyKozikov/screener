import React, { useEffect } from 'react';
import { Box, Autocomplete, TextField, Chip, Typography } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';
import { fetchFilterOptions } from '../../api/metadata';

/**
 * CurrencyFilter Component
 * 
 * Multi-select filter for currency (face unit)
 */
export const CurrencyFilter: React.FC = () => {
  const { draftFilters, setDraftFilter, filterOptions, setFilterOptions } = useFiltersStore();

  // Load filter options on mount
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const options = await fetchFilterOptions();
        setFilterOptions(options);
      } catch (error) {
        console.error('Failed to load filter options:', error);
      }
    };
    
    if (!filterOptions) {
      loadOptions();
    }
  }, [filterOptions, setFilterOptions]);

  const handleCurrencyChange = (_: React.SyntheticEvent<Element, Event>, value: string[]) => {
    setDraftFilter('faceunit', value);
  };

  if (!filterOptions) {
    return null; // Loading...
  }

  return (
    <Autocomplete
      multiple
      size="small"
      options={filterOptions.faceunits || []}
      value={draftFilters.faceunit || []}
      onChange={handleCurrencyChange}
      sx={{ 
        width: '100%',
        '& .MuiAutocomplete-inputRoot': {
          minHeight: '40px',
        },
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={(!draftFilters.faceunit || draftFilters.faceunit.length === 0) ? "Валюта" : ""}
            sx={{
              '& .MuiOutlinedInput-root': {
                paddingRight: '9px !important',
                minHeight: '40px',
                height: '40px',
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
              '& .MuiAutocomplete-endAdornment': {
                right: '9px',
                '& .MuiSvgIcon-root': {
                  fontSize: '1.25rem',
                  color: 'rgba(0, 0, 0, 0.54)',
                },
              },
              '& .MuiAutocomplete-input': {
                padding: '6.5px 4px 6.5px 14px !important',
              },
              '& .MuiInputBase-input::placeholder': {
                fontSize: '0.75rem',
              },
            }}
          />
        )}
        renderTags={(value, getTagProps) =>
          value.map((option, index) => (
            <Chip
              label={option}
              size="small"
              {...getTagProps({ index })}
              key={option}
              sx={{
                margin: '2px',
              }}
            />
          ))
        }
        sx={{
          '& .MuiAutocomplete-tag': {
            margin: '2px',
          },
        }}
      />
  );
};

export default CurrencyFilter;

