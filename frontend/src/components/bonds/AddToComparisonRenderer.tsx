import React from 'react';
import { Box, IconButton } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { ICellRendererParams } from 'ag-grid-community';
import type { BondListItem } from '../../types/bond';
import { useComparisonStore } from '../../stores/comparisonStore';

/**
 * AddToComparisonRenderer Component
 * 
 * Custom cell renderer for "Add to Comparison" column.
 * Uses React hooks and memoization to prevent unnecessary re-renders.
 */
export const AddToComparisonRenderer: React.FC<ICellRendererParams<BondListItem>> = (params) => {
  const bond = params.data;
  const { addBondToComparison, isInComparison } = useComparisonStore();
  
  if (!bond) return null;

  const inComparison = isInComparison(bond.SECID);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click
    if (!inComparison) {
      addBondToComparison(bond);
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
      data-comparison-cell
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
      {inComparison ? (
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
export default React.memo(AddToComparisonRenderer);

