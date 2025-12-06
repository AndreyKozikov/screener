import React from 'react';
import { Box, IconButton } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { ICellRendererParams } from 'ag-grid-community';
import type { BondListItem } from '../../types/bond';
import { usePortfolioStore } from '../../stores/portfolioStore';

/**
 * AddToPortfolioRenderer Component
 * 
 * Custom cell renderer for "Add to Portfolio" column.
 * Uses React hooks and memoization to prevent unnecessary re-renders.
 */
export const AddToPortfolioRenderer: React.FC<ICellRendererParams<BondListItem>> = (params) => {
  const bond = params.data;
  const { addBondToPortfolio, isInPortfolio } = usePortfolioStore();
  
  if (!bond) return null;

  const inPortfolio = isInPortfolio(bond.SECID);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click
    if (!inPortfolio) {
      addBondToPortfolio(bond);
    }
  };

  const handleCellClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click from opening details
    e.preventDefault(); // Prevent default behavior
  };

  const handleCellMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click from opening details
    e.preventDefault(); // Prevent default behavior
  };

  return (
    <Box
      data-portfolio-cell
      onClick={handleCellClick}
      onMouseDown={handleCellMouseDown}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        height: '100%',
        cursor: 'default', // Change cursor to indicate it's not clickable for row selection
      }}
    >
      {inPortfolio ? (
        <CheckCircleIcon
          sx={{
            color: 'success.main',
            fontSize: '1.5rem',
          }}
        />
      ) : (
        <IconButton
          size="small"
          onClick={handleClick}
          sx={{
            color: 'primary.main',
            '&:hover': {
              backgroundColor: 'primary.light',
              color: 'primary.contrastText',
            },
          }}
        >
          <AddIcon fontSize="small" />
        </IconButton>
      )}
    </Box>
  );
};

// Export as stable reference
export default React.memo(AddToPortfolioRenderer);
