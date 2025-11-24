import React from 'react';
import { ThemeProvider, CssBaseline, Box, Typography } from '@mui/material';
import { theme } from './theme/theme';
import { HomePage } from './pages/HomePage';
import { ErrorBoundary } from './components/common/ErrorBoundary';
// import { TestPage } from './TestPage';

/**
 * App Component
 * 
 * Root application component with theme provider
 */
function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <React.Suspense fallback={
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
            <Typography variant="h4">Загрузка...</Typography>
          </Box>
        }>
          <HomePage />
        </React.Suspense>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
