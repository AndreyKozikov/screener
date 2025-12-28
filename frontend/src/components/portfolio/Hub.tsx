import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import PortfolioIcon from '@mui/icons-material/AccountBalanceWallet';
import CalendarIcon from '@mui/icons-material/Event';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import { HubCard } from './HubCard';
import { usePortfolioStore } from '../../stores/portfolioStore';
import type { WorkbenchModule } from './Workbench';

export interface HubProps {
  onModuleSelect: (module: WorkbenchModule) => void;
}

/**
 * Hub Component
 * 
 * Main hub view showing cards for each available module
 * Each card shows module icon, title, value, subtitle, and live badge
 */
export const Hub: React.FC<HubProps> = ({ onModuleSelect }) => {
  const portfolioBonds = usePortfolioStore((state) => state.portfolioBonds);

  // Calculate portfolio statistics for live badges
  const portfolioStats = useMemo(() => {
    const bondCount = portfolioBonds.length;
    
    // Calculate total portfolio value (simplified - would need current prices)
    const totalValue = portfolioBonds.reduce((sum, bond) => {
      const price = bond.PREVPRICE || 0;
      const quantity = bond.quantity || 1;
      const faceValue = bond.FACEVALUE || 0;
      // Approximate value: current price * quantity * faceValue / 100
      return sum + (price * quantity * faceValue / 100);
    }, 0);

    // Find next payment date (simplified - would need coupon data)
    // For now, just show bond count as badge
    const nextPaymentDate = null; // Would need to calculate from coupons

    return {
      bondCount,
      totalValue,
      nextPaymentDate,
    };
  }, [portfolioBonds]);

  // Portfolio card
  const portfolioCard = (
    <HubCard
      title="Портфель"
      value={portfolioStats.bondCount}
      subtitle={`${portfolioStats.bondCount === 1 ? 'облигация' : portfolioStats.bondCount > 1 && portfolioStats.bondCount < 5 ? 'облигации' : 'облигаций'} в портфеле`}
      icon={<PortfolioIcon />}
      color="#1976d2"
      onClick={() => onModuleSelect('PORTFOLIO')}
    />
  );

  // Calendar card
  const calendarCard = (
    <HubCard
      title="Календарь выплат"
      value="—"
      subtitle={portfolioStats.bondCount > 0 ? "График купонных выплат и погашений" : "Добавьте облигации в портфель"}
      icon={<CalendarIcon />}
      color="#4caf50"
      onClick={portfolioStats.bondCount > 0 ? () => onModuleSelect('CALENDAR') : undefined}
      sx={portfolioStats.bondCount === 0 ? { opacity: 0.6 } : {}}
    />
  );

  // Analytics card (placeholder for future analytics)
  const analyticsCard = (
    <HubCard
      title="Аналитика"
      value="—"
      subtitle={portfolioStats.bondCount > 0 ? "Анализ доходности и рисков" : "Добавьте облигации в портфель"}
      icon={<AnalyticsIcon />}
      color="#ff9800"
      onClick={portfolioStats.bondCount > 0 ? () => onModuleSelect('ANALYTICS') : undefined}
      sx={portfolioStats.bondCount === 0 ? { opacity: 0.6 } : {}}
    />
  );

  return (
    <Box 
      sx={{ 
        width: '100%', 
        minHeight: '100vh',
        p: 3,
        background: 'radial-gradient(ellipse at top, rgba(248, 250, 252, 0.8), #F8FAFC)',
        backgroundAttachment: 'fixed',
      }}
    >
      <Typography
        variant="h5"
        sx={{
          fontWeight: 600,
          mb: 3,
          color: 'text.primary',
          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          letterSpacing: '-0.02em',
        }}
      >
        Инструменты портфеля
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 3 }}>
        {portfolioCard}
        {calendarCard}
        {analyticsCard}
      </Box>
    </Box>
  );
};

