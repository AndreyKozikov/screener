import React from 'react';
import { ThemeProvider, CssBaseline, Box, Typography } from '@mui/material';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { theme } from './theme/theme';
import { HomePage } from './pages/HomePage';
import { AgentChatPage } from './pages/AgentChatPage';
import { BlogAdminPage } from './pages/BlogAdminPage';
import { SettingsPage } from './pages/SettingsPage';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { AuthPage } from './pages/AuthPage';
import { AdminCapabilitiesProvider } from './contexts/AdminCapabilitiesProvider';
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
          <BrowserRouter>
            <AdminCapabilitiesProvider>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/login" element={<AuthPage />} />
                <Route path="/agent" element={<AgentChatPage />} />
                <Route path="/blog-admin" element={<BlogAdminPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </AdminCapabilitiesProvider>
          </BrowserRouter>
        </React.Suspense>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;



