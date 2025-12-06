import React, { useEffect } from 'react';
import { Box, Autocomplete, TextField, Chip } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';
import { fetchFilterOptions } from '../../api/metadata';

// Словарь типов облигаций (ключи на английском из bonds_emitent.json)
const BOND_TYPE_LABELS: Record<string, string> = {
  "exchange_bond": "Биржевые облигации",
  "ofz_bond": "Облигации федерального займа",
  "corporate_bond": "Корпоративные облигации",
};

/**
 * BondTypeFilter Component
 * 
 * Multi-select filter for bond type
 */
export const BondTypeFilter: React.FC = () => {
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

  const handleBondTypeChange = (_: React.SyntheticEvent<Element, Event>, value: string[]) => {
    setDraftFilter('bondtype', value);
  };

  if (!filterOptions) {
    return null; // Loading...
  }

  // Фильтруем только те типы, которые есть в словаре BOND_TYPE_LABELS
  const availableBondTypes = (filterOptions.bondtypes || []).filter(
    type => type in BOND_TYPE_LABELS
  );

  return (
    <Autocomplete
      multiple
      size="small"
      options={availableBondTypes}
      value={draftFilters.bondtype || []}
      onChange={handleBondTypeChange}
      getOptionLabel={(option) => BOND_TYPE_LABELS[option] || option}
      sx={{ 
        width: '100%',
        '& .MuiAutocomplete-inputRoot': {
          minHeight: '40px',
        },
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={(!draftFilters.bondtype || draftFilters.bondtype.length === 0) ? "Тип облигации" : ""}
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
              label={BOND_TYPE_LABELS[option] || option}
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

export default BondTypeFilter;

