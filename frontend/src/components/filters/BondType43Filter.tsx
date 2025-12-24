import React from 'react';
import { List, ListItem, Checkbox, FormControlLabel } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';

// Виды облигаций (значения из bonds.json, индекс 43 - BONDTYPE)
const BOND_TYPE43_OPTIONS = [
  'Амортизируемые облигации',
  'Валютные облигации',
  'Конвертируемые облигации',
  'Линкер/облигации с индексируемым',
  'Структурная облигация',
  'Фикс с известным купоном',
  'Фикс с неизвестным купоном',
  'Флоатер',
];

/**
 * BondType43Filter Component
 * 
 * Multi-select filter for bond type 43 (вид облигации из bonds.json) with checkboxes
 */
export const BondType43Filter: React.FC = () => {
  const { draftFilters, setDraftFilter } = useFiltersStore();

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.bondtype43 || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('bondtype43', newValues);
  };

  const selectedValues = draftFilters.bondtype43 || [];

  return (
    <List dense sx={{ width: '100%', py: 0 }}>
      {BOND_TYPE43_OPTIONS.map((option) => (
        <ListItem key={option} disablePadding sx={{ py: 0.5 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={selectedValues.includes(option)}
                onChange={() => handleToggle(option)}
                size="small"
              />
            }
            label={option}
            sx={{ m: 0 }}
          />
        </ListItem>
      ))}
    </List>
  );
};

export default BondType43Filter;

