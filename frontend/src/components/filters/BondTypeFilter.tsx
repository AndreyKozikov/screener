import React, { useEffect } from 'react';
import { List, ListItem, Checkbox, FormControlLabel, Box } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';
import { fetchFilterOptions } from '../../api/metadata';

// Словарь типов облигаций (ключи на английском из bonds_emitent.json)
const BOND_TYPE_LABELS: Record<string, string> = {
  "exchange_bond": "Биржевая облигация",
  "ofz_bond": "ОФЗ (Государственная облигация)",
  "corporate_bond": "Корпоративная облигация",
  "municipal_bond": "Муниципальная облигация",
  "subfederal_bond": "Региональная облигация",
};

/**
 * BondTypeFilter Component
 * 
 * Multi-select filter for bond type with checkboxes
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

  const handleToggle = (value: string) => {
    const currentValues = draftFilters.bondtype || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('bondtype', newValues);
  };

  if (!filterOptions) {
    return <Box>Загрузка...</Box>;
  }

  // Фильтруем только те типы, которые есть в словаре BOND_TYPE_LABELS
  const availableBondTypes = (filterOptions.bondtypes || []).filter(
    type => type in BOND_TYPE_LABELS
  );

  const selectedValues = draftFilters.bondtype || [];

  return (
    <List dense sx={{ width: '100%', py: 0 }}>
      {availableBondTypes.map((type) => (
        <ListItem key={type} disablePadding sx={{ py: 0.5 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={selectedValues.includes(type)}
                onChange={() => handleToggle(type)}
                size="small"
              />
            }
            label={BOND_TYPE_LABELS[type] || type}
            sx={{ m: 0 }}
          />
        </ListItem>
      ))}
    </List>
  );
};

export default BondTypeFilter;

