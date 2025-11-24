import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import FilterAltOffIcon from '@mui/icons-material/FilterAltOff';

interface EmptyStateProps {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
  variant?: 'no-data' | 'no-results';
}

/**
 * EmptyState Component
 * 
 * Displays an empty state with icon, message, and optional action button
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  message,
  icon,
  action,
  variant = 'no-data',
}) => {
  // Default values based on variant
  const defaultTitle = variant === 'no-results' 
    ? 'Ничего не найдено' 
    : 'Нет данных';
    
  const defaultMessage = variant === 'no-results'
    ? 'Попробуйте изменить параметры фильтрации'
    : 'Данные отсутствуют или еще не загружены';
    
  const defaultIcon = variant === 'no-results' 
    ? <SearchOffIcon sx={{ fontSize: 64, color: 'text.disabled' }} />
    : <FilterAltOffIcon sx={{ fontSize: 64, color: 'text.disabled' }} />;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '400px',
        width: '100%',
        py: 6,
        px: 2,
        textAlign: 'center',
      }}
    >
      <Box sx={{ mb: 3 }}>
        {icon || defaultIcon}
      </Box>
      
      <Typography variant="h4" gutterBottom color="text.secondary">
        {title || defaultTitle}
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 400 }}>
        {message || defaultMessage}
      </Typography>
      
      {action && (
        <Button
          variant="contained"
          onClick={action.onClick}
          sx={{ mt: 1 }}
        >
          {action.label}
        </Button>
      )}
    </Box>
  );
};

export default EmptyState;
