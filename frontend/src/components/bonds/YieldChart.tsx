import React, { useMemo } from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useBondsStore } from '../../stores/bondsStore';
import { CHART_CONFIG } from '../../utils/constants';

/**
 * YieldChart Component
 * 
 * Displays a line chart of bond yields/coupons
 */
export const YieldChart: React.FC = () => {
  const { bonds } = useBondsStore();

  // Prepare chart data
  const chartData = useMemo(() => {
    // Get bonds with valid coupon data
    const bondsWithCoupon = bonds
      .filter(b => b.COUPONPERCENT !== null && b.MATDATE !== null)
      .sort((a, b) => {
        const dateA = new Date(a.MATDATE!).getTime();
        const dateB = new Date(b.MATDATE!).getTime();
        return dateA - dateB;
      })
      .slice(0, 50); // Limit to first 50 bonds for readability

    return bondsWithCoupon.map(bond => ({
      name: bond.SECID,
      coupon: bond.COUPONPERCENT,
      yield: bond.YIELDATPREVWAPRICE,
    }));
  }, [bonds]);

  if (chartData.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" gutterBottom fontWeight={600}>
          Доходность облигаций
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          График купонов и доходности (первые 50 облигаций по дате погашения)
        </Typography>
        
        <Box sx={{ width: '100%', height: CHART_CONFIG.HEIGHT }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke={CHART_CONFIG.COLORS.GRID}
              />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12 }}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                label={{ value: '%', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e0e0e0',
                  borderRadius: 8,
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="coupon"
                stroke={CHART_CONFIG.COLORS.PRIMARY}
                strokeWidth={2}
                name="Купон, %"
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="yield"
                stroke={CHART_CONFIG.COLORS.SUCCESS}
                strokeWidth={2}
                name="Доходность, %"
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );
};

export default YieldChart;
