import React from 'react';
import { ThemeProvider, CssBaseline, Box, Typography } from '@mui/material';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { theme } from './theme/theme';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { AdminCapabilitiesProvider } from './contexts/AdminCapabilitiesProvider';

const HomePage = React.lazy(() => import('./pages/HomePage').then(({ HomePage: page }) => ({ default: page })));
const AuthPage = React.lazy(() => import('./pages/AuthPage').then(({ AuthPage: page }) => ({ default: page })));
const AgentChatPage = React.lazy(() => import('./pages/AgentChatPage').then(({ AgentChatPage: page }) => ({ default: page })));
const BlogAdminPage = React.lazy(() => import('./pages/BlogAdminPage').then(({ BlogAdminPage: page }) => ({ default: page })));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage').then(({ SettingsPage: page }) => ({ default: page })));
const AdminPage = React.lazy(() => import('./pages/AdminPage').then(({ AdminPage: page }) => ({ default: page })));
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
                <Route path="/admin" element={<AdminPage />} />
              </Routes>
            </AdminCapabilitiesProvider>
          </BrowserRouter>
        </React.Suspense>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;



