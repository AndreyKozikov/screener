import React from 'react';
import { Box, Button, Typography, alpha } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { PortfolioTable } from './PortfolioTable';

export interface PortfolioModuleProps {
  onBack: () => void;
}

/**
 * PortfolioModule Component
 * 
 * Module view for portfolio management
 * Includes back button and portfolio table
 */
export const PortfolioModule: React.FC<PortfolioModuleProps> = ({ onBack }) => {
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
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={onBack}
          variant="outlined"
          sx={{ 
            minWidth: 'auto',
            px: 2,
            py: 1,
            borderRadius: '12px',
            borderColor: '#E2E8F0',
            color: 'text.primary',
            textTransform: 'none',
            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontWeight: 500,
            backgroundColor: '#ffffff',
            '&:hover': {
              borderColor: '#CBD5E1',
              backgroundColor: '#F8FAFC',
              boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
            },
          }}
        >
          Назад к инструментам
        </Button>
        <Typography 
          variant="h5" 
          sx={{ 
            fontWeight: 600,
            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            letterSpacing: '-0.02em',
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

