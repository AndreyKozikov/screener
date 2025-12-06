import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Divider,
  Paper,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ClearIcon from '@mui/icons-material/Clear';
import { useFiltersStore } from '../../stores/filtersStore';
import { CouponRangeFilter } from './CouponRangeFilter';
import { YieldRangeFilter } from './YieldRangeFilter';
import { CouponYieldRangeFilter } from './CouponYieldRangeFilter';
import { MaturityDateFilter } from './MaturityDateFilter';
import { ListLevelFilter } from './ListLevelFilter';
import { CurrencyFilter } from './CurrencyFilter';
import { BondTypeFilter } from './BondTypeFilter';
import { CouponTypeFilter } from './CouponTypeFilter';
import { RatingRangeFilter } from './RatingRangeFilter';

interface FiltersModalProps {
  open: boolean;
  onClose: () => void;
}

/**
 * FiltersModal Component
 * 
 * Modal dialog containing all bond filtering controls
 * Filters are grouped by category:
 * - Yield/Return filters (coupon yield, yield to maturity, coupon yield to price)
 * - Date filters (maturity date)
 * - Characteristics filters (listing level, currency, bond type, coupon type)
 * - Rating filters
 */
export const FiltersModal: React.FC<FiltersModalProps> = ({ open, onClose }) => {
  const { resetFilters, applyFilters } = useFiltersStore();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  const handleApply = () => {
    applyFilters();
    onClose();
  };

  const handleReset = () => {
    resetFilters();
  };

  const handleCancel = () => {
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleCancel}
      maxWidth="lg"
      fullWidth
      fullScreen={fullScreen}
      PaperProps={{
        sx: {
          maxHeight: '90vh',
          height: fullScreen ? '100vh' : 'auto',
        },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FilterAltIcon color="primary" />
          <Typography variant="h6" component="span" fontWeight={600}>
            ФИЛЬТРЫ
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Группа: Доходность */}
          <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ mb: 2, fontWeight: 600, color: 'primary.main' }}>
              Доходность
            </Typography>
            <Box sx={{ 
              display: 'flex', 
              flexDirection: { xs: 'column', md: 'row' }, 
              gap: 2,
              flexWrap: 'wrap'
            }}>
              {/* Доходность купона относительно номинала */}
              <Box sx={{ flex: { xs: '1 1 100%', md: '1 1 0' }, minWidth: { md: '250px' } }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontSize: '0.875rem' }}>
                  Доходность купона относительно номинала
                </Typography>
                <CouponRangeFilter />
              </Box>

              {/* Доходность к погашению */}
              <Box sx={{ flex: { xs: '1 1 100%', md: '1 1 0' }, minWidth: { md: '250px' } }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontSize: '0.875rem' }}>
                  Доходность к погашению
                </Typography>
                <YieldRangeFilter />
              </Box>

              {/* Доходность купона к текущей цене */}
              <Box sx={{ flex: { xs: '1 1 100%', md: '1 1 0' }, minWidth: { md: '250px' } }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, fontSize: '0.875rem' }}>
                  Доходность купона к текущей цене
                </Typography>
                <CouponYieldRangeFilter />
              </Box>
            </Box>
          </Paper>

          {/* Группа: Дата погашения */}
          <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ mb: 2, fontWeight: 600, color: 'primary.main' }}>
              Дата погашения
            </Typography>
            <MaturityDateFilter />
          </Paper>

          {/* Группа: Характеристики */}
          <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ mb: 2, fontWeight: 600, color: 'primary.main' }}>
              Характеристики облигации
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' }, gap: 2 }}>
              <Box>
                <ListLevelFilter />
              </Box>
              <Box>
                <CurrencyFilter />
              </Box>
              <Box>
                <CouponTypeFilter />
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <BondTypeFilter />
            </Box>
          </Paper>

          {/* Группа: Рейтинг */}
          <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ mb: 2, fontWeight: 600, color: 'primary.main' }}>
              Рейтинг
            </Typography>
            <RatingRangeFilter />
          </Paper>
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          onClick={handleReset}
          startIcon={<ClearIcon />}
          variant="outlined"
          color="secondary"
        >
          Сбросить
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={handleCancel} variant="outlined">
          Отмена
        </Button>
        <Button onClick={handleApply} variant="contained" color="primary">
          Применить
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FiltersModal;
