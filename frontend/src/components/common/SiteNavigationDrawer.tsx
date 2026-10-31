import React, { useState } from 'react';
import {
  Box,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

export type SiteNavigationItem = {
  id: string;
  label: string;
  icon?: React.ReactNode;
  children?: SiteNavigationItem[];
};

type SiteNavigationDrawerProps = {
  activeId: string;
  items: SiteNavigationItem[];
  onSelect: (id: string) => void;
};

const containsActiveItem = (item: SiteNavigationItem, activeId: string): boolean =>
  item.id === activeId || Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));

const NavigationRow: React.FC<{
  item: SiteNavigationItem;
  activeId: string;
  depth: number;
  onSelect: (id: string) => void;
}> = ({ item, activeId, depth, onSelect }) => {
  const isSelected = item.id === activeId;
  const hasActiveChild = !isSelected && Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));

  return (
    <Box component="li" sx={{ listStyle: 'none' }}>
      <ListItemButton
        component="button"
        selected={isSelected}
        aria-current={isSelected ? 'page' : undefined}
        onClick={() => onSelect(item.id)}
        sx={{
          position: 'relative',
          minHeight: depth === 0 ? 46 : 40,
          px: depth === 0 ? 1.25 : 1,
          py: 0.55,
          borderRadius: 2,
          color: isSelected ? '#1558A6' : hasActiveChild ? '#244D7B' : '#334B6D',
          '&:hover': { bgcolor: 'rgba(25,118,210,0.075)' },
          '&.Mui-selected': {
            bgcolor: 'rgba(25,118,210,0.105)',
            color: '#1558A6',
            '&:hover': { bgcolor: 'rgba(25,118,210,0.14)' },
            '&::before': {
              content: '""',
              position: 'absolute',
              left: 0,
              top: 8,
              bottom: 8,
              width: 3,
              borderRadius: 3,
              bgcolor: '#1976d2',
            },
          },
          '&:focus-visible': { outline: '2px solid rgba(25,118,210,0.48)', outlineOffset: 1 },
        }}
      >
        {depth === 0 && item.icon && (
          <ListItemIcon sx={{ minWidth: 34, color: 'inherit', '& svg': { fontSize: 19 } }}>
            {item.icon}
          </ListItemIcon>
        )}
        {depth > 0 && (
          <Box
            aria-hidden="true"
            sx={{
              width: 6,
              height: 6,
              flex: '0 0 auto',
              mr: 1.25,
              ml: 0.35,
              borderRadius: '50%',
              bgcolor: isSelected ? '#1976d2' : '#9CB2CF',
            }}
          />
        )}
        <ListItemText
          primary={item.label}
          primaryTypographyProps={{
            fontSize: depth === 0 ? '0.9rem' : '0.855rem',
            lineHeight: 1.35,
            fontWeight: isSelected ? 650 : hasActiveChild ? 600 : depth === 0 ? 550 : 450,
          }}
        />
      </ListItemButton>

      {item.children && item.children.length > 0 && (
        <Box
          component="ul"
          sx={{
            m: 0,
            mt: 0.45,
            mb: 0.7,
            ml: depth === 0 ? 2.05 : 1.7,
            pl: 1.15,
            borderLeft: '1px solid #D9E5F3',
            listStyle: 'none',
          }}
        >
          {item.children.map((child) => (
            <NavigationRow
              key={child.id}
              item={child}
              activeId={activeId}
              depth={depth + 1}
              onSelect={onSelect}
            />
          ))}
        </Box>
      )}
    </Box>
  );
};

export const SiteNavigationDrawer: React.FC<SiteNavigationDrawerProps> = ({
  activeId,
  items,
  onSelect,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const panelWidth = { xs: 'min(76vw, 300px)', sm: 320 };

  return (
    <Box
      component="aside"
      id="site-navigation-drawer"
      aria-label="Навигация по сайту"
      sx={{
        position: 'sticky',
        top: 0,
        alignSelf: 'flex-start',
        zIndex: (theme) => theme.zIndex.appBar + 1,
        flex: '0 0 auto',
        width: isExpanded ? panelWidth : 0,
        height: isExpanded ? '100dvh' : 0,
        minHeight: isExpanded ? '100vh' : 0,
        overflow: 'visible',
        transition: 'width 260ms cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}
    >
      {isExpanded ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            width: panelWidth,
            height: '100dvh',
            minHeight: '100vh',
            color: '#17345B',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.985), rgba(247,250,255,0.98))',
            borderRight: '1px solid #E7EEF7',
            boxShadow: '8px 0 24px rgba(29, 61, 103, 0.08)',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.25,
              pt: 1.5,
              pb: 1.25,
              minHeight: 64,
              borderBottom: '1px solid #E7EEF7',
            }}
          >
          <IconButton
            aria-label="Свернуть меню разделов"
            aria-controls="site-navigation-drawer"
            aria-expanded="true"
            onClick={() => setIsExpanded(false)}
            sx={{
              flex: '0 0 auto',
              width: 36,
              height: 36,
              borderRadius: 2,
              color: '#29476F',
              bgcolor: 'rgba(25,118,210,0.075)',
              border: '1px solid rgba(216,228,242,0.92)',
              '&:hover': { bgcolor: 'rgba(25,118,210,0.12)' },
            }}
          >
            <ChevronLeftIcon />
          </IconButton>

            <Box
              aria-hidden="true"
              sx={{
                width: 34,
                height: 34,
                flex: '0 0 auto',
                display: 'grid',
                placeItems: 'center',
                borderRadius: 2,
                color: '#1976d2',
                bgcolor: 'rgba(25,118,210,0.09)',
                border: '1px solid rgba(25,118,210,0.10)',
                '& svg': { fontSize: 18 },
              }}
            >
              <AccountTreeOutlinedIcon />
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography component="h2" sx={{ color: '#17345B', fontWeight: 700, fontSize: '0.96rem', lineHeight: 1.25 }}>
                Разделы сайта
              </Typography>
              <Typography sx={{ color: '#7185A0', fontSize: '0.72rem', mt: 0.2 }}>
                Выберите нужный инструмент
              </Typography>
            </Box>
          </Box>

          <Box
            id="site-navigation-items"
            component="nav"
            aria-label="Разделы сайта"
            sx={{ flex: 1, overflowY: 'auto', px: 1.25, py: 1.5, scrollbarWidth: 'thin' }}
          >
            <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 0.4 }}>
              {items.map((item, index) => (
                <React.Fragment key={item.id}>
                  {index === 1 && (
                    <Box component="li" aria-hidden="true" sx={{ listStyle: 'none', py: 0.65, px: 1.25 }}>
                      <Box sx={{ height: '1px', bgcolor: '#E7EEF7' }} />
                    </Box>
                  )}
                  <NavigationRow item={item} activeId={activeId} depth={0} onSelect={onSelect} />
                </React.Fragment>
              ))}
            </Box>
          </Box>

          <Box sx={{ px: 2.25, py: 1.5, borderTop: '1px solid #E7EEF7' }}>
            <Typography sx={{ color: '#8799B0', fontSize: '0.73rem', letterSpacing: '0.02em' }}>
              BondsScreener
            </Typography>
          </Box>
        </Box>
      ) : (
        <IconButton
          aria-label="Открыть меню разделов"
          aria-controls="site-navigation-drawer"
          aria-expanded="false"
          onClick={() => setIsExpanded(true)}
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            zIndex: (theme) => theme.zIndex.appBar + 1,
            width: 42,
            height: 52,
            borderRadius: '0 0 12px 0',
            color: '#29476F',
            bgcolor: 'rgba(255,255,255,0.88)',
            border: '1px solid rgba(216,228,242,0.92)',
            boxShadow: '0 3px 12px rgba(29,61,103,0.12)',
            '&:hover': { bgcolor: '#FFFFFF' },
          }}
        >
          <ChevronRightIcon />
        </IconButton>
      )}
    </Box>
  );
};
