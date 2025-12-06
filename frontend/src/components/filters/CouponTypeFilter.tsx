import React from 'react';
import { Autocomplete, TextField, Chip } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * CouponTypeFilter Component
 * 
 * Multi-select filter for coupon type (FIX or FLOAT)
 */
export const CouponTypeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const couponTypeOptions = [
    { value: 'FIX', label: 'постоянный' },
    { value: 'FLOAT', label: 'плавающий' },
  ];

  const getLabel = (value: string) => {
    return couponTypeOptions.find(opt => opt.value === value)?.label || value;
  };

  const handleCouponTypeChange = (_: React.SyntheticEvent<Element, Event>, value: string[]) => {
    setDraftFilter('couponType', value);
  };

  return (
    <Autocomplete
      multiple
      size="small"
      options={couponTypeOptions.map(opt => opt.value)}
      getOptionLabel={(option) => getLabel(option)}
      value={draftFilters.couponType || []}
      onChange={handleCouponTypeChange}
      sx={{ 
        width: '100%',
        '& .MuiAutocomplete-inputRoot': {
          minHeight: '40px',
        },
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={(!draftFilters.couponType || draftFilters.couponType.length === 0) ? "Тип купона" : ""}
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
            label={getLabel(option)}
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

export default CouponTypeFilter;
