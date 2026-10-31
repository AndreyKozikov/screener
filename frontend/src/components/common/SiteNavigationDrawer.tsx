import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
  Paper,
  Typography,
  Tooltip,
  Popper,
  Fade,
  ClickAwayListener,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ShowChartIcon from '@mui/icons-material/ShowChart';

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

const NAV_EXPANDED_STORAGE_KEY = 'bonds-screener:nav-expanded';

const containsActiveItem = (item: SiteNavigationItem, activeId: string): boolean =>
  item.id === activeId || Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));

// ─── Collapsed-mode: icon-only row with Click-to-Open Popper & Hover Tooltip ───

const CollapsedRow: React.FC<{
  item: SiteNavigationItem;
  activeId: string;
  isOpen: boolean;
  onToggleOpen: () => void;
  onClose: () => void;
  onSelect: (id: string) => void;
}> = ({ item, activeId, isOpen, onToggleOpen, onClose, onSelect }) => {
  const anchorRef = useRef<HTMLButtonElement>(null);
  const isActive = containsActiveItem(item, activeId);
  const hasChildren = Boolean(item.children?.length);

  const handleClick = () => {
    if (hasChildren) {
      onToggleOpen();
    } else {
      onClose();
      onSelect(item.id);
    }
  };

  const handleClickAway = (event: MouseEvent | TouchEvent) => {
    const target = event.target as Node | null;
    if (!target) return;

    // Игнорируем клики по самой кнопке
    if (anchorRef.current && anchorRef.current.contains(target)) {
      return;
    }

    // Игнорируем клики внутри панели навигации — соседние кнопки сами обработают открытие/закрытие
    const navDrawer = document.getElementById('site-navigation-drawer');
    if (navDrawer && navDrawer.contains(target)) {
      return;
    }

    onClose();
  };

  return (
    <Box sx={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
      {/* Tooltip always shown on hover, unless menu is currently open */}
      <Tooltip
        title={item.label}
        placement="right"
        arrow
        disableHoverListener={isOpen}
        slotProps={{
          tooltip: {
            sx: {
              bgcolor: '#17345B',
              color: '#FFFFFF',
              fontSize: '0.8rem',
              fontWeight: 500,
              boxShadow: '0 4px 14px rgba(29,61,103,0.18)',
              py: 0.6,
              px: 1.2,
              borderRadius: 1.5,
            },
          },
          arrow: { sx: { color: '#17345B' } },
        }}
      >
        <ListItemButton
          ref={anchorRef}
          component="button"
          selected={isActive || isOpen}
          onClick={handleClick}
          aria-current={item.id === activeId ? 'page' : undefined}
          aria-expanded={hasChildren ? isOpen : undefined}
          sx={{
            width: 44,
            height: 44,
            mx: 'auto',
            justifyContent: 'center',
            borderRadius: '12px',
            color: isActive || isOpen ? '#1558A6' : '#2a4060',
            bgcolor: isActive || isOpen ? 'rgba(255,255,255,0.6)' : 'transparent',
            boxShadow: isActive || isOpen ? '0 2px 8px rgba(25,118,210,0.15)' : 'none',
            position: 'relative',
            '&:hover': {
              bgcolor: isActive || isOpen ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.45)',
              color: '#1558A6',
            },
            '&.Mui-selected': {
              bgcolor: 'rgba(255,255,255,0.65)',
              color: '#1558A6',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.8)' },
              '&::before': {
                content: '""',
                position: 'absolute',
                left: -6,
                top: 10,
                bottom: 10,
                width: 3,
                borderRadius: 3,
                bgcolor: '#1976d2',
              },
            },
            '&:focus-visible': { outline: '2px solid rgba(25,118,210,0.48)', outlineOffset: 1 },
          }}
        >
          <ListItemIcon
            sx={{
              minWidth: 0,
              color: 'inherit',
              justifyContent: 'center',
              '& svg': { fontSize: 21 },
            }}
          >
            {item.icon}
          </ListItemIcon>
        </ListItemButton>
      </Tooltip>

      {/* Popper menu opens strictly on click for items with subcategories */}
      {hasChildren && (
        <Popper
          open={isOpen}
          anchorEl={anchorRef.current}
          placement="right-start"
          transition
          disablePortal={false}
          modifiers={[
            {
              name: 'offset',
              options: { offset: [0, 10] },
            },
            {
              name: 'preventOverflow',
              options: { boundary: 'viewport', padding: 8 },
            },
          ]}
          sx={{ zIndex: 1500 }}
        >
          {({ TransitionProps }) => (
            <Fade {...TransitionProps} timeout={180}>
              <div>
                <ClickAwayListener onClickAway={handleClickAway}>
                  <Paper
                    elevation={8}
                    sx={{
                      minWidth: 220,
                      maxWidth: 280,
                      borderRadius: 2.5,
                      overflow: 'hidden',
                      background: 'linear-gradient(180deg, rgba(240,247,255,0.98) 0%, rgba(246,250,255,0.97) 100%)',
                      backdropFilter: 'blur(20px)',
                      WebkitBackdropFilter: 'blur(20px)',
                      border: '1px solid rgba(255,255,255,0.85)',
                      boxShadow: '0 8px 32px rgba(29,61,103,0.15), 0 2px 8px rgba(29,61,103,0.06)',
                      py: 0.8,
                    }}
                  >
                    {/* Header = parent category label */}
                    <Box
                      sx={{
                        px: 2,
                        pt: 1,
                        pb: 0.8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        borderBottom: '1px solid rgba(200,218,240,0.5)',
                        mb: 0.5,
                      }}
                    >
                      {item.icon && (
                        <Box sx={{ color: '#1558A6', display: 'flex', alignItems: 'center', '& svg': { fontSize: 18 } }}>
                          {item.icon}
                        </Box>
                      )}
                      <Typography
                        sx={{
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          color: '#1558A6',
                          letterSpacing: '0.02em',
                        }}
                      >
                        {item.label}
                      </Typography>
                    </Box>

                    {/* Sub-items */}
                    <Box sx={{ py: 0.2 }}>
                      {item.children!.map((child) => {
                        const childActive = child.id === activeId;
                        return (
                          <ListItemButton
                            key={child.id}
                            component="button"
                            selected={childActive}
                            onClick={() => {
                              onClose();
                              onSelect(child.id);
                            }}
                            sx={{
                              px: 2,
                              py: 0.7,
                              minHeight: 36,
                              borderRadius: 1.5,
                              mx: 0.8,
                              color: childActive ? '#1558A6' : '#2a4060',
                              fontSize: '0.84rem',
                              bgcolor: childActive ? 'rgba(255,255,255,0.7)' : 'transparent',
                              '&:hover': { bgcolor: 'rgba(255,255,255,0.6)' },
                              '&.Mui-selected': {
                                bgcolor: 'rgba(255,255,255,0.75)',
                                color: '#1558A6',
                                fontWeight: 650,
                                '&:hover': { bgcolor: 'rgba(255,255,255,0.85)' },
                              },
                            }}
                          >
                            <Box
                              aria-hidden="true"
                              sx={{
                                width: 5,
                                height: 5,
                                flex: '0 0 auto',
                                mr: 1.25,
                                borderRadius: '50%',
                                bgcolor: childActive ? '#1976d2' : 'rgba(156,178,207,0.8)',
                              }}
                            />
                            <Typography
                              sx={{
                                fontSize: '0.84rem',
                                fontWeight: childActive ? 650 : 450,
                                lineHeight: 1.35,
                              }}
                            >
                              {child.label}
                            </Typography>
                          </ListItemButton>
                        );
                      })}
                    </Box>
                  </Paper>
                </ClickAwayListener>
              </div>
            </Fade>
          )}
        </Popper>
      )}
    </Box>
  );
};

// ─── Expanded-mode: full-width row with collapsible accordion ────────────────

const ExpandedRow: React.FC<{
  item: SiteNavigationItem;
  activeId: string;
  depth: number;
  onSelect: (id: string) => void;
}> = ({ item, activeId, depth, onSelect }) => {
  const isSelected = item.id === activeId;
  const hasActiveChild = !isSelected && Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));
  const hasChildren = Boolean(item.children?.length);

  const [expanded, setExpanded] = useState(() => hasActiveChild || isSelected);

  // Auto-expand when a child becomes active
  useEffect(() => {
    if (hasActiveChild) {
      setExpanded(true);
    }
  }, [hasActiveChild]);

  const handleClick = () => {
    if (hasChildren) {
      setExpanded((prev) => !prev);
    } else {
      onSelect(item.id);
    }
  };

  return (
    <Box component="li" sx={{ listStyle: 'none' }}>
      <ListItemButton
        component="button"
        selected={isSelected}
        aria-current={isSelected ? 'page' : undefined}
        onClick={handleClick}
        sx={{
          position: 'relative',
          minHeight: depth === 0 ? 46 : 38,
          px: depth === 0 ? 1.4 : 1.2,
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
              width: 3.5,
              borderRadius: 3,
              bgcolor: '#1976d2',
            },
          },
          '&:focus-visible': { outline: '2px solid rgba(25,118,210,0.48)', outlineOffset: 1 },
        }}
      >
        {depth === 0 && item.icon && (
          <ListItemIcon sx={{ minWidth: 34, color: 'inherit', '& svg': { fontSize: 20 } }}>
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
            fontSize: depth === 0 ? '0.895rem' : '0.845rem',
            lineHeight: 1.35,
            fontWeight: isSelected ? 650 : hasActiveChild ? 600 : depth === 0 ? 550 : 450,
          }}
        />
        {hasChildren && depth === 0 && (
          <Box
            sx={{
              color: 'inherit',
              opacity: 0.6,
              display: 'flex',
              alignItems: 'center',
              ml: 0.5,
              transition: 'transform 0.2s ease',
            }}
          >
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </Box>
        )}
      </ListItemButton>

      {hasChildren && (
        <Collapse in={expanded} timeout="auto" unmountOnExit={false}>
          <Box
            component="ul"
            sx={{
              m: 0,
              mt: 0.4,
              mb: 0.7,
              ml: depth === 0 ? 2.1 : 1.7,
              pl: 1.2,
              borderLeft: '1px solid rgba(200,218,240,0.6)',
              listStyle: 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 0.3,
            }}
          >
            {item.children!.map((child) => (
              <ExpandedRow
                key={child.id}
                item={child}
                activeId={activeId}
                depth={depth + 1}
                onSelect={onSelect}
              />
            ))}
          </Box>
        </Collapse>
      )}
    </Box>
  );
};

// ─── Shared constants ────────────────────────────────────────────────────────

const TRANSITION_DURATION = 300;
const EASING = 'cubic-bezier(0.4, 0, 0.2, 1)';
const RAIL_WIDTH = 64;

// ─── Main component ──────────────────────────────────────────────────────────

export const SiteNavigationDrawer: React.FC<SiteNavigationDrawerProps> = ({
  activeId,
  items,
  onSelect,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Track which collapsed item's popup is currently open
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Initialize expanded state with memory / responsiveness
  const [isExpanded, setIsExpanded] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    try {
      const saved = window.sessionStorage.getItem(NAV_EXPANDED_STORAGE_KEY);
      if (saved !== null) {
        return JSON.parse(saved) as boolean;
      }
    } catch {
      // fallback
    }
    // Default: collapsed on smaller screens, expanded on larger
    return !window.matchMedia('(max-width: 1024px)').matches;
  });

  const toggleExpanded = useCallback(() => {
    setOpenMenuId(null);
    setIsExpanded((prev) => {
      const next = !prev;
      try {
        window.sessionStorage.setItem(NAV_EXPANDED_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const expandedPanelWidth = isMobile ? 'min(80vw, 290px)' : 280;

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
        width: isExpanded ? expandedPanelWidth : RAIL_WIDTH,
        height: '100dvh',
        minHeight: '100vh',
        overflow: 'visible',
        transition: `width ${TRANSITION_DURATION}ms ${EASING}`,
      }}
    >
      {/* ── Collapsed rail (icon-only, shown when isExpanded = false) ── */}
      <Box
        aria-hidden={isExpanded}
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          display: 'flex',
          flexDirection: 'column',
          width: RAIL_WIDTH,
          height: '100dvh',
          minHeight: '100vh',
          color: '#17345B',
          background: 'linear-gradient(180deg, rgba(235,244,255,0.95) 0%, rgba(241,247,255,0.92) 100%)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRight: '1px solid rgba(255,255,255,0.72)',
          boxShadow: '8px 0 24px rgba(29, 61, 103, 0.06)',
          opacity: isExpanded ? 0 : 1,
          pointerEvents: isExpanded ? 'none' : 'auto',
          visibility: isExpanded ? 'hidden' : 'visible',
          transition: [
            `opacity ${TRANSITION_DURATION}ms ${EASING}`,
            `visibility 0ms ${isExpanded ? `${TRANSITION_DURATION}ms` : '0ms'}`,
          ].join(', '),
        }}
      >
        {/* Header with logo button to expand (inspired by top hexagon on screenshot) */}
        <Box
          sx={{
            height: 60,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid rgba(200,218,240,0.4)',
          }}
        >
          <Tooltip title="Развернуть панель" placement="right" arrow>
            <IconButton
              onClick={toggleExpanded}
              aria-label="Развернуть панель навигации"
              sx={{
                width: 42,
                height: 42,
                borderRadius: '12px',
                color: '#1558A6',
                bgcolor: 'rgba(255,255,255,0.7)',
                boxShadow: '0 2px 8px rgba(29,61,103,0.08)',
                '&:hover': {
                  bgcolor: '#FFFFFF',
                  transform: 'scale(1.05)',
                },
                transition: 'all 0.2s ease',
              }}
            >
              <ChevronRightIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Navigation icon items list */}
        <Box
          component="nav"
          aria-label="Разделы сайта"
          sx={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'visible',
            px: 0.5,
            py: 1.5,
            scrollbarWidth: 'none',
            '&::-webkit-scrollbar': { display: 'none' },
            display: 'flex',
            flexDirection: 'column',
            gap: 0.6,
          }}
        >
          {items.map((item) => (
            <CollapsedRow
              key={item.id}
              item={item}
              activeId={activeId}
              isOpen={openMenuId === item.id}
              onToggleOpen={() => setOpenMenuId((prev) => (prev === item.id ? null : item.id))}
              onClose={() => setOpenMenuId(null)}
              onSelect={onSelect}
            />
          ))}
        </Box>

        {/* Compact footer (avatar/badge like on screenshot) */}
        <Box
          sx={{
            py: 1.5,
            borderTop: '1px solid rgba(200,218,240,0.5)',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <Tooltip title="BondsScreener" placement="right" arrow>
            <Box
              sx={{
                width: 38,
                height: 38,
                borderRadius: '10px',
                bgcolor: 'rgba(25,118,210,0.12)',
                border: '1px solid rgba(25,118,210,0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                '&:hover': {
                  bgcolor: 'rgba(25,118,210,0.2)',
                  transform: 'scale(1.05)',
                },
              }}
              onClick={toggleExpanded}
            >
              <ShowChartIcon sx={{ fontSize: 20, color: '#1558A6' }} />
            </Box>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Expanded panel (full width, shown when isExpanded = true) ── */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          display: 'flex',
          flexDirection: 'column',
          width: expandedPanelWidth,
          height: '100dvh',
          minHeight: '100vh',
          color: '#17345B',
          background: 'linear-gradient(180deg, rgba(235,244,255,0.95) 0%, rgba(241,247,255,0.92) 100%)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRight: '1px solid rgba(255,255,255,0.72)',
          boxShadow: '8px 0 24px rgba(29, 61, 103, 0.06)',
          opacity: isExpanded ? 1 : 0,
          transform: isExpanded ? 'translateX(0)' : 'translateX(-24px)',
          pointerEvents: isExpanded ? 'auto' : 'none',
          visibility: isExpanded ? 'visible' : 'hidden',
          transition: [
            `opacity ${TRANSITION_DURATION}ms ${EASING}`,
            `transform ${TRANSITION_DURATION}ms ${EASING}`,
            `visibility 0ms ${isExpanded ? '0ms' : `${TRANSITION_DURATION}ms`}`,
          ].join(', '),
        }}
      >
        {/* Header: Logo + Title + Collapse Button (like CodingLab on screenshot) */}
        <Box
          sx={{
            height: 60,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 1.8,
            borderBottom: '1px solid rgba(200,218,240,0.4)',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}>
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: '9px',
                bgcolor: 'rgba(25,118,210,0.12)',
                border: '1px solid rgba(25,118,210,0.22)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#1558A6',
              }}
            >
              <ShowChartIcon sx={{ fontSize: 20 }} />
            </Box>
            <Typography
              sx={{
                fontSize: '1rem',
                fontWeight: 700,
                color: '#1558A6',
                letterSpacing: '-0.01em',
              }}
            >
              BondsScreener
            </Typography>
          </Box>

          <IconButton
            aria-label="Свернуть меню разделов"
            onClick={toggleExpanded}
            tabIndex={isExpanded ? 0 : -1}
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              color: '#29476F',
              bgcolor: 'rgba(255,255,255,0.7)',
              border: '1px solid rgba(216,228,242,0.9)',
              boxShadow: '0 2px 6px rgba(29,61,103,0.06)',
              '&:hover': { bgcolor: '#FFFFFF' },
            }}
          >
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        </Box>

        {/* Navigation items list */}
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
          <Box
            component="ul"
            sx={{ m: 0, p: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 0.4 }}
          >
            {items.map((item, index) => (
              <React.Fragment key={item.id}>
                {index === 1 && (
                  <Box component="li" aria-hidden="true" sx={{ listStyle: 'none', py: 0.5, px: 1 }}>
                    <Box sx={{ height: '1px', bgcolor: 'rgba(200,218,240,0.5)' }} />
                  </Box>
                )}
                <ExpandedRow item={item} activeId={activeId} depth={0} onSelect={onSelect} />
              </React.Fragment>
            ))}
          </Box>
        </Box>

        {/* Footer profile card (inspired by bottom card on screenshot) */}
        <Box
          sx={{
            p: 1.5,
            borderTop: '1px solid rgba(200,218,240,0.5)',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.25,
              p: 1,
              borderRadius: 2,
              bgcolor: 'rgba(255,255,255,0.45)',
              border: '1px solid rgba(255,255,255,0.7)',
            }}
          >
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: '10px',
                bgcolor: '#1558A6',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.8rem',
                flexShrink: 0,
                boxShadow: '0 2px 6px rgba(21,88,166,0.3)',
              }}
            >
              BS
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography
                noWrap
                sx={{
                  fontSize: '0.83rem',
                  fontWeight: 650,
                  color: '#17345B',
                  lineHeight: 1.2,
                }}
              >
                Bonds Screener
              </Typography>
              <Typography
                noWrap
                sx={{
                  fontSize: '0.72rem',
                  color: 'rgba(100,120,150,0.85)',
                  lineHeight: 1.2,
                  mt: 0.2,
                }}
              >
                Аналитический терминал
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
