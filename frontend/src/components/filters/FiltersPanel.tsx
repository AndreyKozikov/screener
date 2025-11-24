import React from 'react';
import { Card, CardContent, Box, Typography, Button, Divider } from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ClearIcon from '@mui/icons-material/Clear';
import { useFiltersStore } from '../../stores/filtersStore';
import { SearchFilter } from './SearchFilter';
import { CouponRangeFilter } from './CouponRangeFilter';
import { MaturityDateFilter } from './MaturityDateFilter';
import { ListLevelFilter } from './ListLevelFilter';
import { CurrencyFilter } from './CurrencyFilter';

/**
 * FiltersPanel Component
 * 
 * Main panel containing all bond filtering controls
 */
export const FiltersPanel: React.FC = () => {
  const { resetFilters } = useFiltersStore();

  const handleReset = () => {
    resetFilters();
  };

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <FilterAltIcon color="primary" />
            <Typography variant="h6" fontWeight={600}>
              Фильтры
            </Typography>
          </Box>
          <Button
            fullWidth
            size="small"
            startIcon={<ClearIcon />}
            onClick={handleReset}
            variant="outlined"
            color="secondary"
          >
            Сбросить
          </Button>
        </Box>

        <Divider sx={{ mb: 3 }} />

        {/* Filters */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Search */}
          <SearchFilter />

          {/* Coupon Range */}
          <CouponRangeFilter />

          {/* Maturity Date Range */}
          <MaturityDateFilter />

          {/* List Level Filter */}
          <ListLevelFilter />

          {/* Currency Filter */}
          <CurrencyFilter />
        </Box>
      </CardContent>
    </Card>
  );
};

export default FiltersPanel;
