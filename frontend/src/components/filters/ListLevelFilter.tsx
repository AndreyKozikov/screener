import React, { useEffect } from 'react';
import { List, ListItem, Checkbox, FormControlLabel, Box } from '@mui/material';
import { useFiltersStore } from '../../stores/filtersStore';
import { fetchFilterOptions } from '../../api/metadata';

/**
 * ListLevelFilter Component
 * 
 * Multi-select filter for list level with checkboxes
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

  const handleToggle = (value: number) => {
    const currentValues = draftFilters.listlevel || [];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(v => v !== value)
      : [...currentValues, value];
    setDraftFilter('listlevel', newValues);
  };

  if (!filterOptions) {
    return <Box>Загрузка...</Box>;
  }

  const selectedValues = draftFilters.listlevel || [];
  const sortedLevels = [...(filterOptions.listlevels || [])].sort((a, b) => a - b);

  return (
    <List dense sx={{ width: '100%', py: 0 }}>
      {sortedLevels.map((level) => (
        <ListItem key={level} disablePadding sx={{ py: 0.5 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={selectedValues.includes(level)}
                onChange={() => handleToggle(level)}
                size="small"
              />
            }
            label={`Уровень ${level}`}
            sx={{ m: 0 }}
          />
        </ListItem>
      ))}
    </List>
  );
};

export default ListLevelFilter;
