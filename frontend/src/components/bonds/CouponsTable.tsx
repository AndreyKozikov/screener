import React from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import type { Coupon } from '../../types/coupon';
import { formatDate, formatNumber, formatPercent } from '../../utils/formatters';

interface CouponsTableProps {
  coupons: Coupon[];
  isLoading?: boolean;
  error?: string | null;
  currency?: string | null;  // Валюта из faceunit
}

/**
 * CouponsTable Component
 * 
 * Displays coupon payments in a table format
 */
export const CouponsTable: React.FC<CouponsTableProps> = ({
  coupons,
  isLoading = false,
  error = null,
  currency = null,
}) => {
  // Get currency from first coupon if not provided
  const displayCurrency = currency || coupons[0]?.faceunit || '';
  const couponAmountHeader = displayCurrency 
    ? `Сумма купона, ${displayCurrency}`
    : 'Сумма купона';
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
        <CircularProgress size={24} />
        <Typography variant="body2" sx={{ ml: 2, color: 'text.secondary' }}>
          Загрузка данных о купонах...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!coupons || coupons.length === 0) {
    return (
      <Box sx={{ py: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          Данные о купонных выплатах отсутствуют
        </Typography>
      </Box>
    );
  }

  return (
    <TableContainer component={Paper} elevation={0} sx={{ mt: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600 }}>Дата купона</TableCell>
            <TableCell align="center" sx={{ fontWeight: 600 }}>
              {couponAmountHeader}
            </TableCell>
            <TableCell align="center" sx={{ fontWeight: 600 }}>
              Ставка купона
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {coupons.map((coupon, index) => (
            <TableRow key={index} hover>
              <TableCell>
                {coupon.coupondate ? formatDate(coupon.coupondate) : '—'}
              </TableCell>
              <TableCell align="center">
                {coupon.value !== null && coupon.value !== undefined
                  ? formatNumber(coupon.value, 2)
                  : '—'}
              </TableCell>
              <TableCell align="center">
                {coupon.valueprc !== null && coupon.valueprc !== undefined
                  ? formatPercent(coupon.valueprc)
                  : '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default CouponsTable;

