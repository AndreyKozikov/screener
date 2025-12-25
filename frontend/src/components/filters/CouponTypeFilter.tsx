import React from 'react';
import { List, ListItem, Checkbox, FormControlLabel } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

/**
 * CouponTypeFilter Component
 * 
 * Multi-select filter for coupon type (FIX or FLOAT) with checkboxes
 */
export const CouponTypeFilter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const couponTypeOptions = [
    { value: 'FIX', label: 'постоянный' },
    { value: 'FLOAT', label: 'плавающий' },
  ];

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.couponType || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('couponType', newValues);
  };

  const selectedValues = draftFilters.couponType || [];

  return (
    <List dense sx={{ width: '100%', py: 0 }}>
      {couponTypeOptions.map((option) => (
        <ListItem key={option.value} disablePadding sx={{ py: 0.5 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={selectedValues.includes(option.value)}
                onChange={() => handleToggle(option.value)}
      size="small"
              />
            }
            label={option.label}
            sx={{ m: 0 }}
          />
        </ListItem>
      ))}
    </List>
  );
};

export default CouponTypeFilter;
