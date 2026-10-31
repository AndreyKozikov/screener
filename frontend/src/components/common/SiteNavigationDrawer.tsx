import React, { useState } from 'react';
import {
  Box,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
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
          color: isSelected ? '#1558A6' : hasActiveChild ? '#1a4a7a' : '#2a4060',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.45)' },
          '&.Mui-selected': {
            bgcolor: 'rgba(255,255,255,0.55)',
            color: '#1558A6',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.65)' },
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
              bgcolor: isSelected ? '#1976d2' : 'rgba(156,178,207,0.8)',
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
            borderLeft: '1px solid rgba(200,218,240,0.6)',
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

/** Shared styling for the expand / collapse toggle button */
const toggleButtonSx = {
  width: 42,
  height: 52,
  borderRadius: '0 0 12px 0',
  color: '#29476F',
  bgcolor: 'rgba(255,255,255,0.88)',
  border: '1px solid rgba(216,228,242,0.92)',
  boxShadow: '0 3px 12px rgba(29,61,103,0.12)',
  '&:hover': { bgcolor: '#FFFFFF' },
} as const;

/** Duration (ms) and easing shared by every animated property */
const TRANSITION_DURATION = 320;
const EASING = 'cubic-bezier(0.4, 0, 0.2, 1)';

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
        height: '100dvh',
        minHeight: '100vh',
        overflow: 'visible',
        transition: `width ${TRANSITION_DURATION}ms ${EASING}`,
      }}
    >
      {/* ── Expanded panel (always mounted, animated via CSS) ── */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          display: 'flex',
          flexDirection: 'column',
          width: panelWidth,
          height: '100dvh',
          minHeight: '100vh',
          color: '#17345B',
          background: 'linear-gradient(180deg, rgba(235,244,255,0.95) 0%, rgba(241,247,255,0.92) 100%)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRight: '1px solid rgba(255,255,255,0.72)',
          boxShadow: '8px 0 24px rgba(29, 61, 103, 0.06)',
          // Slide + fade animation
          opacity: isExpanded ? 1 : 0,
          transform: isExpanded ? 'translateX(0)' : 'translateX(-24px)',
          pointerEvents: isExpanded ? 'auto' : 'none',
          visibility: isExpanded ? 'visible' : 'hidden',
          transition: [
            `opacity ${TRANSITION_DURATION}ms ${EASING}`,
            `transform ${TRANSITION_DURATION}ms ${EASING}`,
            // Keep visible during the closing fade, then hide
            `visibility 0ms ${isExpanded ? '0ms' : `${TRANSITION_DURATION}ms`}`,
          ].join(', '),
        }}
      >
        {/* Collapse button — top-right corner */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            px: 0,
            pt: 0,
          }}
        >
          <IconButton
            aria-label="Свернуть меню разделов"
            aria-controls="site-navigation-drawer"
            aria-expanded="true"
            onClick={() => setIsExpanded(false)}
            tabIndex={isExpanded ? 0 : -1}
            sx={{
              ...toggleButtonSx,
              borderRadius: '0 0 0 12px',
            }}
          >
            <ChevronLeftIcon />
          </IconButton>
        </Box>

        {/* Navigation items — scrollbar hidden */}
        <Box
          id="site-navigation-items"
          component="nav"
          aria-label="Разделы сайта"
          sx={{
            flex: 1,
            overflowY: 'auto',
            px: 1.25,
            py: 1.5,
            scrollbarWidth: 'none',
            '&::-webkit-scrollbar': { display: 'none' },
          }}
        >
          <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 0.4 }}>
            {items.map((item, index) => (
              <React.Fragment key={item.id}>
                {index === 1 && (
                  <Box component="li" aria-hidden="true" sx={{ listStyle: 'none', py: 0.65, px: 1.25 }}>
                    <Box sx={{ height: '1px', bgcolor: 'rgba(200,218,240,0.5)' }} />
                  </Box>
                )}
                <NavigationRow item={item} activeId={activeId} depth={0} onSelect={onSelect} />
              </React.Fragment>
            ))}
          </Box>
        </Box>

        {/* Footer */}
        <Box sx={{ px: 2.25, py: 1.5, borderTop: '1px solid rgba(200,218,240,0.5)' }}>
          <Typography sx={{ color: 'rgba(100,120,150,0.8)', fontSize: '0.73rem', letterSpacing: '0.02em' }}>
            BondsScreener
          </Typography>
        </Box>
      </Box>

      {/* ── Expand button (always mounted, cross-fades with panel) ── */}
      <IconButton
        aria-label="Открыть меню разделов"
        aria-controls="site-navigation-drawer"
        aria-expanded="false"
        onClick={() => setIsExpanded(true)}
        tabIndex={isExpanded ? -1 : 0}
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          zIndex: (theme) => theme.zIndex.appBar + 1,
          ...toggleButtonSx,
          opacity: isExpanded ? 0 : 1,
          transform: isExpanded ? 'scale(0.85)' : 'scale(1)',
          pointerEvents: isExpanded ? 'none' : 'auto',
          visibility: isExpanded ? 'hidden' : 'visible',
          transition: [
            `opacity ${TRANSITION_DURATION}ms ${EASING}`,
            `transform ${TRANSITION_DURATION}ms ${EASING}`,
            `visibility 0ms ${isExpanded ? `${TRANSITION_DURATION}ms` : '0ms'}`,
          ].join(', '),
        }}
      >
        <ChevronRightIcon />
      </IconButton>
    </Box>
  );
};
