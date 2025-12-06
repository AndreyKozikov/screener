import React, { useState } from 'react';
import { Card, CardContent, Box, Typography, Button, Divider, Collapse, IconButton } from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useFiltersStore } from '../../stores/filtersStore';
import { SearchFilter } from './SearchFilter';
import { CouponRangeFilter } from './CouponRangeFilter';
import { YieldRangeFilter } from './YieldRangeFilter';
import { CouponYieldRangeFilter } from './CouponYieldRangeFilter';
import { MaturityDateFilter } from './MaturityDateFilter';
import { ListLevelFilter } from './ListLevelFilter';
import { CurrencyFilter } from './CurrencyFilter';
import { BondTypeFilter } from './BondTypeFilter';
import { CouponTypeFilter } from './CouponTypeFilter';
import { RatingRangeFilter } from './RatingRangeFilter';

/**
 * FiltersPanel Component
 * 
 * Main panel containing all bond filtering controls
 * Filters are arranged horizontally
 * Can be collapsed to save space
 */
export const FiltersPanel: React.FC = () => {
  const { resetFilters, applyFilters } = useFiltersStore();
  const [isExpanded, setIsExpanded] = useState(false); // По умолчанию свернуто

  const handleReset = () => {
    resetFilters();
  };
  
  const handleApply = () => {
    applyFilters();
  };

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <Card sx={{ width: '100%' }}>
      <CardContent sx={{ pb: isExpanded ? 2 : '16px !important' }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FilterAltIcon color="primary" />
            <Typography variant="h6" fontWeight={600}>
              ФИЛЬТРЫ
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              size="small"
              onClick={handleApply}
              variant="contained"
              color="primary"
              sx={{
                minHeight: '25.5px',
                fontSize: '0.75rem',
                py: 0.5,
                px: 2,
              }}
            >
              Применить
            </Button>
            <Button
              size="small"
              startIcon={<ClearIcon />}
              onClick={handleReset}
              variant="outlined"
              color="secondary"
              sx={{
                minHeight: '25.5px',
                fontSize: '0.75rem',
                py: 0.5,
                '& .MuiButton-startIcon': {
                  marginRight: '4px',
                  '& > *:nth-of-type(1)': {
                    fontSize: '1rem'
                  }
                }
              }}
            >
              Сбросить
            </Button>
            <IconButton
              onClick={handleToggle}
              size="small"
              sx={{ ml: 1 }}
              aria-label={isExpanded ? 'Свернуть фильтры' : 'Развернуть фильтры'}
            >
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>
        </Box>

        {/* Collapsible Content */}
        <Collapse in={isExpanded}>
          <Divider sx={{ my: 2 }} />
          {/* Filters - Horizontal Layout */}
          <Box sx={{ display: 'flex', flexDirection: 'row', gap: 2, flexWrap: 'wrap', width: '100%', justifyContent: 'flex-start' }}>
            <Box sx={{ width: '300px', flexShrink: 0 }}>
              <SearchFilter />
            </Box>
            <Box sx={{ width: '250px', flexShrink: 0 }}>
              <Box sx={{ mb: 0.5 }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                  Доходность купона относительно номинала
                </Typography>
              </Box>
              <CouponRangeFilter />
            </Box>
            <Box sx={{ width: '250px', flexShrink: 0 }}>
              <Box sx={{ mb: 0.5 }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                  Доходность к погашению
                </Typography>
              </Box>
              <YieldRangeFilter />
            </Box>
            <Box sx={{ width: '250px', flexShrink: 0 }}>
              <Box sx={{ mb: 0.5 }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                  Доходность купона к текущей цене
                </Typography>
              </Box>
              <CouponYieldRangeFilter />
            </Box>
            <Box sx={{ width: '400px', flexShrink: 0 }}>
              <MaturityDateFilter />
            </Box>
            <Box sx={{ width: '180px', flexShrink: 0 }}>
              <ListLevelFilter />
            </Box>
          <Box sx={{ width: '180px', flexShrink: 0 }}>
            <CurrencyFilter />
          </Box>
          <Box sx={{ width: '500px', flexShrink: 0 }}>
            <BondTypeFilter />
          </Box>
          <Box sx={{ width: '180px', flexShrink: 0 }}>
            <CouponTypeFilter />
          </Box>
          <Box sx={{ width: '250px', flexShrink: 0 }}>
            <Box sx={{ mb: 0.5 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                Рейтинг
              </Typography>
            </Box>
            <RatingRangeFilter />
          </Box>
        </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default FiltersPanel;
