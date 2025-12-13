import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Collapse,
  IconButton,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ClearIcon from '@mui/icons-material/Clear';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
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
 * Each filter is in its own collapsible section with independent expand/collapse state
 */
export const FiltersModal: React.FC<FiltersModalProps> = ({ open, onClose }) => {
  const { resetFilters, applyFilters } = useFiltersStore();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  // State for each filter's expand/collapse
  const [showCouponRange, setShowCouponRange] = useState(false);
  const [showYieldRange, setShowYieldRange] = useState(false);
  const [showCouponYieldRange, setShowCouponYieldRange] = useState(false);
  const [showMaturityDate, setShowMaturityDate] = useState(false);
  const [showListLevel, setShowListLevel] = useState(false);
  const [showCurrency, setShowCurrency] = useState(false);
  const [showBondType, setShowBondType] = useState(false);
  const [showCouponType, setShowCouponType] = useState(false);
  const [showRating, setShowRating] = useState(false);

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

      <DialogContent dividers sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {/* Доходность купона относительно номинала и Доходность купона к текущей цене в одну строку */}
          <Box sx={{ display: 'flex', gap: 1.5, flexDirection: { xs: 'column', md: 'row' }, alignItems: 'flex-start' }}>
              {/* Доходность купона относительно номинала */}
            <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50', flex: 1 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle1" fontSize="0.85rem">
                  Доходность купона относительно номинала
                </Typography>
                <IconButton 
                  onClick={() => setShowCouponRange(!showCouponRange)}
                  sx={{ 
                    border: 'none !important', 
                    boxShadow: 'none !important', 
                    outline: 'none !important',
                    '&:hover': { bgcolor: 'transparent' },
                    '&:focus': { outline: 'none !important', border: 'none !important' },
                    '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                    '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                    '&::before': { display: 'none' },
                    '&::after': { display: 'none' }
                  }}
                  size="small"
                  disableRipple
                  disableFocusRipple
                >
                  {showCouponRange ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                </IconButton>
              </Box>
              <Collapse in={showCouponRange}>
                <Box mt={1.5}>
                <CouponRangeFilter />
              </Box>
              </Collapse>
              </Box>

              {/* Доходность купона к текущей цене */}
            <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50', flex: 1 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle1" fontSize="0.85rem">
                  Доходность купона к текущей цене
                </Typography>
                <IconButton 
                  onClick={() => setShowCouponYieldRange(!showCouponYieldRange)}
                  sx={{ 
                    border: 'none !important', 
                    boxShadow: 'none !important', 
                    outline: 'none !important',
                    '&:hover': { bgcolor: 'transparent' },
                    '&:focus': { outline: 'none !important', border: 'none !important' },
                    '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                    '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                    '&::before': { display: 'none' },
                    '&::after': { display: 'none' }
                  }}
                  size="small"
                  disableRipple
                  disableFocusRipple
                >
                  {showCouponYieldRange ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                </IconButton>
              </Box>
              <Collapse in={showCouponYieldRange}>
                <Box mt={1.5}>
                <CouponYieldRangeFilter />
              </Box>
              </Collapse>
            </Box>
          </Box>

          {/* Доходность к погашению */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
                Доходность к погашению
              </Typography>
              <IconButton 
                onClick={() => setShowYieldRange(!showYieldRange)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showYieldRange ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showYieldRange}>
              <Box mt={1.5}>
                <YieldRangeFilter />
              </Box>
            </Collapse>
            </Box>

          {/* Дата погашения */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
              Дата погашения
            </Typography>
              <IconButton 
                onClick={() => setShowMaturityDate(!showMaturityDate)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showMaturityDate ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showMaturityDate}>
              <Box mt={1.5}>
            <MaturityDateFilter />
              </Box>
            </Collapse>
          </Box>

          {/* Уровень листинга */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
                Уровень листинга
            </Typography>
              <IconButton 
                onClick={() => setShowListLevel(!showListLevel)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showListLevel ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showListLevel}>
              <Box mt={1.5}>
                <ListLevelFilter />
              </Box>
            </Collapse>
          </Box>

          {/* Валюта */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
                Валюта
              </Typography>
              <IconButton 
                onClick={() => setShowCurrency(!showCurrency)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showCurrency ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showCurrency}>
              <Box mt={1.5}>
                <CurrencyFilter />
              </Box>
            </Collapse>
              </Box>

          {/* Тип облигации */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
                Тип облигации
              </Typography>
              <IconButton 
                onClick={() => setShowBondType(!showBondType)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showBondType ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showBondType}>
              <Box mt={1.5}>
              <BondTypeFilter />
            </Box>
            </Collapse>
          </Box>

          {/* Тип купона */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
                Тип купона
              </Typography>
              <IconButton 
                onClick={() => setShowCouponType(!showCouponType)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showCouponType ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showCouponType}>
              <Box mt={1.5}>
                <CouponTypeFilter />
              </Box>
            </Collapse>
          </Box>

          {/* Рейтинг */}
          <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'grey.50' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" fontSize="0.85rem">
              Рейтинг
            </Typography>
              <IconButton 
                onClick={() => setShowRating(!showRating)}
                sx={{ 
                  border: 'none !important', 
                  boxShadow: 'none !important', 
                  outline: 'none !important',
                  '&:hover': { bgcolor: 'transparent' },
                  '&:focus': { outline: 'none !important', border: 'none !important' },
                  '&:focus-visible': { outline: 'none !important', border: 'none !important' },
                  '&:active': { outline: 'none !important', boxShadow: 'none !important', border: 'none !important' },
                  '&::before': { display: 'none' },
                  '&::after': { display: 'none' }
                }}
                size="small"
                disableRipple
                disableFocusRipple
              >
                {showRating ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={showRating}>
              <Box mt={1.5}>
            <RatingRangeFilter />
              </Box>
            </Collapse>
          </Box>
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
