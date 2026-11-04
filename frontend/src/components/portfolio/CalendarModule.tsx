import React from 'react';
import { Box, Typography, alpha } from '@mui/material';
import { PaymentCalendar } from './PaymentCalendar';

/**
 * CalendarModule Component
 * 
 * Module view for payment calendar
 * Includes the payment calendar
 */
export const CalendarModule: React.FC = () => {
  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#F4F7FD' }}>
      {/* Glassmorphism sticky header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          px: { xs: 1.5, sm: 2 },
          py: 1.5,
          position: 'sticky',
          top: 0,
          zIndex: 10,
          backgroundColor: alpha('#ffffff', 0.8),
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid #E2E8F0',
          boxShadow: '0 2px 8px rgba(16, 38, 74, 0.04)',
        }}
      >
        <Typography 
          variant="h5" 
          sx={{ 
            fontWeight: 600,
            fontFamily: 'var(--app-font-family)',
            letterSpacing: '0.005em',
            color: '#10264A',
          }}
        >
          Календарь выплат
        </Typography>
      </Box>

      {/* Calendar content */}
      <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto' }}>
        <PaymentCalendar />
      </Box>
    </Box>
  );
};




