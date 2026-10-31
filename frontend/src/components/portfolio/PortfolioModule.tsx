import React from 'react';
import { Box, Typography, alpha } from '@mui/material';
import { PortfolioTable } from './PortfolioTable';

/**
 * PortfolioModule Component
 * 
 * Module view for portfolio management
 * Includes the portfolio table
 */
export const PortfolioModule: React.FC = () => {
  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#F8FAFC' }}>
      {/* Glassmorphism sticky header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          p: 2,
          position: 'sticky',
          top: 0,
          zIndex: 10,
          backgroundColor: alpha('#ffffff', 0.8),
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(226, 232, 240, 0.5)',
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <Typography 
          variant="h5" 
          sx={{ 
            fontWeight: 600,
            fontFamily: 'var(--app-font-family)',
            letterSpacing: '0.005em',
          }}
        >
          Портфель
        </Typography>
      </Box>

      {/* Portfolio table content */}
      <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <PortfolioTable />
      </Box>
    </Box>
  );
};




