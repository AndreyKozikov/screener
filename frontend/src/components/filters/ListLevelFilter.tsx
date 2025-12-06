import React, { useEffect } from 'react';
import { Box, Autocomplete, TextField, Chip, Typography } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';
import { fetchFilterOptions } from '../../api/metadata';

/**
 * ListLevelFilter Component
 * 
 * Multi-select filter for list level
 */
export const ListLevelFilter: React.FC = () => {
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

  const handleListLevelChange = (_: React.SyntheticEvent<Element, Event>, value: number[]) => {
    setDraftFilter('listlevel', value);
  };

  if (!filterOptions) {
    return null; // Loading...
  }

  return (
    <Autocomplete
      multiple
      size="small"
      options={filterOptions.listlevels || []}
      value={draftFilters.listlevel || []}
      onChange={handleListLevelChange}
      sx={{ 
        width: '100%',
        '& .MuiAutocomplete-inputRoot': {
          minHeight: '32px',
        },
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={(!draftFilters.listlevel || draftFilters.listlevel.length === 0) ? "Уровень листинга" : ""}
            sx={{
              '& .MuiOutlinedInput-root': {
                paddingRight: '9px !important',
                minHeight: '32px',
                height: '32px',
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
                padding: '4px 4px 4px 14px !important',
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

export default ListLevelFilter;
