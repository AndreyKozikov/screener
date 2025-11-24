import React from 'react';
import { Card, CardContent, Box, Typography, Grid } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import FilterListIcon from '@mui/icons-material/FilterList';
import { useBondsStore } from '../../stores/bondsStore';
import { formatNumber } from '../../utils/formatters';

/**
 * BondMetrics Component
 * 
 * Displays summary metrics about the bonds dataset
 */
export const BondMetrics: React.FC = () => {
  const { totalBonds, filteredCount, bonds } = useBondsStore();

  // Calculate average coupon
  const avgCoupon = React.useMemo(() => {
    if (bonds.length === 0) return 0;
    const validBonds = bonds.filter(b => b.COUPONPERCENT !== null);
    if (validBonds.length === 0) return 0;
    const sum = validBonds.reduce((acc, b) => acc + (b.COUPONPERCENT || 0), 0);
    return sum / validBonds.length;
  }, [bonds]);

  return (
    <Grid container spacing={2}>
      {/* Total Bonds */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <AccountBalanceIcon color="primary" />
              <Typography variant="h6" color="text.secondary">
                Всего облигаций
              </Typography>
            </Box>
            <Typography variant="h3" fontWeight={700}>
              {formatNumber(totalBonds, 0)}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Filtered Count */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <FilterListIcon color="primary" />
              <Typography variant="h6" color="text.secondary">
                После фильтров
              </Typography>
            </Box>
            <Typography variant="h3" fontWeight={700}>
              {formatNumber(filteredCount, 0)}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Average Coupon */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <TrendingUpIcon color="success" />
              <Typography variant="h6" color="text.secondary">
                Средний купон
              </Typography>
            </Box>
            <Typography variant="h3" fontWeight={700}>
              {formatNumber(avgCoupon, 2)}%
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Displayed */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="h6" color="text.secondary">
                Отображено
              </Typography>
            </Box>
            <Typography variant="h3" fontWeight={700}>
              {formatNumber(bonds.length, 0)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              из {formatNumber(filteredCount, 0)}
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default BondMetrics;
