import React from 'react';
import { ThemeProvider, CssBaseline, Box, Typography } from '@mui/material';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { theme } from './theme/theme';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { AdminCapabilitiesProvider } from './contexts/AdminCapabilitiesProvider';

const HomePage = React.lazy(() => import('./pages/HomePage').then(({ HomePage: page }) => ({ default: page })));
const AuthPage = React.lazy(() => import('./pages/AuthPage').then(({ AuthPage: page }) => ({ default: page })));
const AgentChatPage = React.lazy(() => import('./pages/AgentChatPage').then(({ AgentChatPage: page }) => ({ default: page })));
const BlogAdminPage = React.lazy(() => import('./pages/BlogAdminPage').then(({ BlogAdminPage: page }) => ({ default: page })));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage').then(({ SettingsPage: page }) => ({ default: page })));
const AdminPage = React.lazy(() => import('./pages/AdminPage').then(({ AdminPage: page }) => ({ default: page })));
const AgentLogsAdminPage = React.lazy(() => import('./pages/AgentLogsAdminPage').then(({ AgentLogsAdminPage: page }) => ({ default: page })));
const DataUpdatesAdminPage = React.lazy(() => import('./pages/DataUpdatesAdminPage').then(({ DataUpdatesAdminPage: page }) => ({ default: page })));
const BondDetails = React.lazy(() => import('./components/bonds/BondDetails').then(m => ({default: m.BondDetails})));
const BondPreview = React.lazy(() => import('./components/bonds/BondPreview'));

function AppRoutes() {
  const location = useLocation();
  const background = location.pathname.startsWith('/bonds/') && location.state?.tableLocation;
  return <>
    <Routes location={background || location}>
                <Route path="/" element={<HomePage />} />
                <Route path="/bonds/:id" element={<BondDetails />} />
                <Route path="/bonds/:id/preview" element={<BondPreview />} />
                <Route path="/login" element={<AuthPage />} />
                <Route path="/agent" element={<AgentChatPage />} />
                <Route path="/blog-admin" element={<BlogAdminPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/agent-logs" element={<AgentLogsAdminPage />} />
          <Route path="/admin/data-updates" element={<DataUpdatesAdminPage />} />
              </Routes>
    {background && <React.Suspense fallback={null}><Routes>
      <Route path="/bonds/:id/preview" element={<BondPreview />} />
      <Route path="/bonds/:id" element={<BondDetails />} />
    </Routes></React.Suspense>}
  </>;
}

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
              <AppRoutes />
            </AdminCapabilitiesProvider>
          </BrowserRouter>
        </React.Suspense>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;



