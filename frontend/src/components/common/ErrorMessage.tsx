import React from 'react';
import { Box, Alert, AlertTitle, Button } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  severity?: 'error' | 'warning' | 'info';
}

/**
 * ErrorMessage Component
 * 
 * Displays an error/warning message with optional retry button
 */
export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'Ошибка',
  message,
  onRetry,
  severity = 'error',
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '300px',
        width: '100%',
        py: 4,
        px: 2,
      }}
    >
      <Alert
        severity={severity}
        sx={{
          maxWidth: 600,
          width: '100%',
        }}
      >
        <AlertTitle>{title}</AlertTitle>
        {message}
        {onRetry && (
          <Box sx={{ mt: 2 }}>
            <Button
              size="small"
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={onRetry}
              color={severity === 'error' ? 'error' : 'primary'}
            >
              Попробовать снова
            </Button>
          </Box>
        )}
      </Alert>
    </Box>
  );
};

export default ErrorMessage;
