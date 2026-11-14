import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import { SiteNavigationDrawer } from '../components/common/SiteNavigationDrawer';
import { AgentChat } from '../components/agent/AgentChat';
import {
  getSiteNavigationItems,
  isPortfolioNavigationId,
  resolveSiteNavigationTarget,
  writeSavedHomePageView,
} from '../utils/siteNavigation';
import { isAuthenticated, PORTFOLIO_AUTH_REDIRECT_STATE } from '../utils/auth';

/**
 * Отдельная страница диалога с ИИ-ассистентом.
 * Выдержана в стиле главной страницы: стеклянный фон, та же боковая панель
 * навигации, та же шапка. Открывается после отправки запроса из строки
 * запроса на главной странице.
 */
export const AgentChatPage: React.FC = () => {
  const navigate = useNavigate();

  const handleSiteNavigationSelect = (id: string) => {
    if (id === 'chat') {
      return;
    }
    if (isPortfolioNavigationId(id) && !isAuthenticated()) {
      navigate('/login', { state: PORTFOLIO_AUTH_REDIRECT_STATE });
      return;
    }
    writeSavedHomePageView(resolveSiteNavigationTarget(id));
    navigate('/');
  };

  const handleGoHome = () => {
    writeSavedHomePageView(resolveSiteNavigationTarget('home'));
    navigate('/');
  };

  return (
    <Box sx={{
      display: 'flex',
      height: '100vh',
      width: '100%',
      overflow: 'hidden',
      '@supports (height: 100dvh)': { height: '100dvh' },
      bgcolor: '#EAF3FF',
      backgroundImage: 'linear-gradient(180deg, rgba(236,244,255,0.08), rgba(236,244,255,0.18)), url("/images/bond-glass-background.png")',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundAttachment: 'fixed',
    }}>
      <SiteNavigationDrawer
        activeId="chat"
        items={getSiteNavigationItems(isAuthenticated())}
        onSelect={handleSiteNavigationSelect}
        onOpenAdmin={() => navigate('/admin')}
      />

      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: '1 1 0',
        minWidth: 0,
        minHeight: 0,
        height: '100%',
        overflowY: 'auto',
        overscrollBehaviorY: 'contain',
      }}>
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            top: 0,
            zIndex: (theme) => theme.zIndex.appBar,
            bgcolor: 'rgba(255,255,255,0.48)',
            color: '#10264A',
            borderBottom: '1px solid rgba(255,255,255,0.72)',
            backdropFilter: 'blur(20px)',
          }}
        >
          <Toolbar sx={{ minHeight: { xs: '52px !important', md: '62px !important' }, px: { xs: 1, md: 3.5 }, py: 0 }}>
            <Box sx={{
              display: 'grid',
              gridTemplateColumns: { xs: 'minmax(0, 1fr) auto', md: 'auto minmax(0, 1fr) auto' },
              alignItems: 'center',
              columnGap: { xs: 0.5, md: 1.5 },
              width: '100%',
              maxWidth: 1660,
              mx: 'auto',
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.75, sm: 1.5 }, gridColumn: '1 / 2', gridRow: '1 / 2', minWidth: 0 }}>
                <AccountBalanceIcon sx={{ fontSize: { xs: 22, sm: 27 }, color: '#17345B' }} />
                <Typography
                  variant="body1"
                  component="h1"
                  fontWeight={600}
                  sx={{
                    fontFamily: 'var(--app-font-family)',
                    letterSpacing: '0.005em',
                    fontSize: { xs: '0.75rem', sm: '1rem' },
                  }}
                >
                  ИИ-ассистент BondsScreener
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: { xs: 0.25, sm: 0.75 }, gridColumn: { xs: '2 / 3', md: '3 / 4' }, gridRow: '1 / 2' }}>
                <Tooltip title="Вернуться в разделы">
                  <IconButton
                    size="small"
                    aria-label="Вернуться в разделы"
                    onClick={handleGoHome}
                    sx={{
                      color: '#29476F',
                      bgcolor: 'rgba(255,255,255,0.42)',
                      border: '1px solid rgba(255,255,255,0.72)',
                      width: { xs: 30, sm: 38 },
                      height: { xs: 30, sm: 38 },
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.72)', color: '#5B3BE8' },
                    }}
                  >
                    <HomeOutlinedIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          </Toolbar>
        </AppBar>

        <Box sx={{
          flexGrow: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: 'calc(100dvh - 62px)',
          px: { xs: 1.25, md: 3.5, xl: 4.5 },
          py: { xs: 1.25, md: 2 },
        }}>
          <AgentChat />
        </Box>
      </Box>
    </Box>
  );
};

export default AgentChatPage;
