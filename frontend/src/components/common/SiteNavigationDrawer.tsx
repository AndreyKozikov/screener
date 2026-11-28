import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box,
  Collapse,
  Drawer,
  IconButton,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
  Tooltip,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AdminPanelSettingsOutlinedIcon from '@mui/icons-material/AdminPanelSettingsOutlined';
import { useAdminCapabilities } from '../../contexts/adminCapabilitiesContext';

export type SiteNavigationGroup = 'data' | 'work' | 'content';

export type SiteNavigationItem = {
  id: string;
  label: string;
  icon?: React.ReactNode;
  children?: SiteNavigationItem[];
  requiresAuth?: boolean;
  group?: SiteNavigationGroup;
};

type SiteNavigationDrawerProps = {
  activeId: string;
  items: SiteNavigationItem[];
  onSelect: (id: string) => void;
  onOpenAdmin?: () => void;
};

const NAV_EXPANDED_STORAGE_KEY = 'bonds-screener:nav-expanded';

// ─── Общие размеры и типографика панели ─────────────────────────────────────

const TRANSITION_DURATION = 300;
const EASING = 'cubic-bezier(0.4, 0, 0.2, 1)';
const RAIL_WIDTH = 64;
const PANEL_WIDTH = 300;
const MOBILE_PANEL_WIDTH = 'min(86vw, 320px)';

const ICON_SLOT_WIDTH = 24;
const ICON_SIZE = 20;

const TEXT_ITEM = '0.9375rem';
const TEXT_SUB_ITEM = '0.875rem';
const TEXT_GROUP = '0.8125rem';
const TEXT_META = '0.8125rem';

const HOVER_MEDIA = '@media (hover: hover) and (pointer: fine)';
const REDUCED_MOTION = '@media (prefers-reduced-motion: reduce)';

const containsActiveItem = (item: SiteNavigationItem, activeId: string): boolean =>
  item.id === activeId || Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));

const isGroupStart = (items: SiteNavigationItem[], index: number): boolean =>
  index > 0 && items[index - 1]?.group !== items[index]?.group;

// ─── Свёрнутый рельс: иконка, tooltip и меню подразделов ────────────────────

const CollapsedRow: React.FC<{
  item: SiteNavigationItem;
  activeId: string;
  isOpen: boolean;
  isMobile: boolean;
  onToggleOpen: () => void;
  onClose: () => void;
  onSelect: (id: string) => void;
}> = ({ item, activeId, isOpen, isMobile, onToggleOpen, onClose, onSelect }) => {
  const theme = useTheme();
  const anchorRef = useRef<HTMLButtonElement>(null);
  const isActive = containsActiveItem(item, activeId);
  const hasChildren = Boolean(item.children?.length);
  const isHighlighted = isActive || isOpen;

  const primary = theme.palette.primary.main;
  const activeColor = theme.palette.primary.dark;
  const textColor = theme.palette.text.primary;
  const selectedBg = alpha(primary, 0.1);
  const selectedHoverBg = alpha(primary, 0.16);

  const handleClick = () => {
    if (hasChildren) {
      onToggleOpen();
    } else {
      onClose();
      onSelect(item.id);
    }
  };

  return (
    <Box sx={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
      <Tooltip
        title={item.label}
        placement="right"
        arrow
        disableHoverListener={isOpen}
        slotProps={{
          tooltip: {
            sx: {
              bgcolor: theme.palette.text.primary,
              color: theme.palette.background.paper,
              fontSize: TEXT_META,
              fontWeight: 500,
              boxShadow: theme.shadows[3],
              py: 0.6,
              px: 1.2,
              borderRadius: 1,
            },
          },
          arrow: { sx: { color: theme.palette.text.primary } },
        }}
      >
        <ListItemButton
          ref={anchorRef}
          component="button"
          selected={isHighlighted}
          onClick={handleClick}
          aria-label={item.label}
          aria-current={item.id === activeId ? 'page' : undefined}
          aria-haspopup={hasChildren && !isMobile ? 'menu' : undefined}
          aria-expanded={hasChildren && !isMobile ? isOpen : undefined}
          sx={{
            width: 44,
            height: 44,
            mx: 'auto',
            justifyContent: 'center',
            borderRadius: 1.5,
            color: isHighlighted ? activeColor : textColor,
            bgcolor: isHighlighted ? selectedBg : 'transparent',
            position: 'relative',
            transition: 'background-color 150ms ease, color 150ms ease',
            [HOVER_MEDIA]: {
              '&:hover': {
                bgcolor: isHighlighted ? selectedHoverBg : alpha(primary, 0.06),
                color: activeColor,
              },
            },
            '&.Mui-selected': {
              bgcolor: selectedBg,
              color: activeColor,
              [HOVER_MEDIA]: {
                '&:hover': { bgcolor: selectedHoverBg },
              },
            },
            '&:focus-visible': { outline: `2px solid ${alpha(primary, 0.48)}`, outlineOffset: 1 },
            [REDUCED_MOTION]: { transition: 'none' },
          }}
        >
          <ListItemIcon
            sx={{
              minWidth: 0,
              color: 'inherit',
              justifyContent: 'center',
              '& svg': { fontSize: ICON_SIZE },
            }}
          >
            {item.icon}
          </ListItemIcon>
        </ListItemButton>
      </Tooltip>

      {hasChildren && !isMobile && (
        <Menu
          open={isOpen}
          anchorEl={anchorRef.current}
          onClose={onClose}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          slotProps={{
            paper: {
              sx: {
                ml: 1,
                minWidth: 240,
                maxWidth: 300,
                borderRadius: 2,
                border: `1px solid ${theme.palette.divider}`,
                boxShadow: theme.shadows[8],
                bgcolor: theme.palette.background.paper,
                backgroundImage: 'none',
              },
            },
            list: {
              'aria-label': item.label,
              sx: { py: 0.75 },
            },
          }}
        >
          {/* Заголовок меню: название родительского раздела */}
          <MenuItem
            disabled
            disableRipple
            sx={{
              minHeight: 0,
              px: 1.5,
              py: 0.75,
              mb: 0.5,
              gap: 1,
              borderBottom: `1px solid ${theme.palette.divider}`,
              borderRadius: 0,
              opacity: '1 !important',
              '&.Mui-disabled': { opacity: 1 },
            }}
          >
            {item.icon && (
              <Box
                sx={{
                  color: activeColor,
                  display: 'flex',
                  alignItems: 'center',
                  '& svg': { fontSize: 18 },
                }}
              >
                {item.icon}
              </Box>
            )}
            <Typography
              sx={{
                fontSize: TEXT_GROUP,
                fontWeight: 600,
                color: activeColor,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                lineHeight: 1.4,
              }}
            >
              {item.label}
            </Typography>
          </MenuItem>

          {item.children!.map((child) => {
            const childActive = child.id === activeId;
            return (
              <MenuItem
                key={child.id}
                selected={childActive}
                onClick={() => {
                  onClose();
                  onSelect(child.id);
                }}
                sx={{
                  mx: 1,
                  px: 1.5,
                  minHeight: 40,
                  borderRadius: 1.5,
                  color: childActive ? activeColor : textColor,
                  fontSize: TEXT_SUB_ITEM,
                  bgcolor: childActive ? selectedBg : 'transparent',
                  [HOVER_MEDIA]: {
                    '&:hover': { bgcolor: alpha(primary, 0.06) },
                  },
                  '&.Mui-selected': {
                    bgcolor: selectedBg,
                    color: activeColor,
                    [HOVER_MEDIA]: {
                      '&:hover': { bgcolor: selectedHoverBg },
                    },
                  },
                }}
              >
                <Box
                  aria-hidden="true"
                  sx={{
                    width: 5,
                    height: 5,
                    flex: '0 0 auto',
                    mr: 1,
                    borderRadius: '50%',
                    bgcolor: childActive ? primary : theme.palette.text.disabled,
                  }}
                />
                <Typography
                  sx={{
                    fontSize: TEXT_SUB_ITEM,
                    fontWeight: childActive ? 600 : 400,
                    lineHeight: 1.35,
                  }}
                >
                  {child.label}
                </Typography>
              </MenuItem>
            );
          })}
        </Menu>
      )}
    </Box>
  );
};

// ─── Развёрнутая панель: строка со сворачиваемым списком подразделов ────────

const ExpandedRow: React.FC<{
  item: SiteNavigationItem;
  activeId: string;
  depth: number;
  onSelect: (id: string) => void;
  forceExpand?: boolean;
}> = ({ item, activeId, depth, onSelect, forceExpand }) => {
  const theme = useTheme();
  const isSelected = item.id === activeId;
  const hasActiveChild = !isSelected && Boolean(item.children?.some((child) => containsActiveItem(child, activeId)));
  const hasChildren = Boolean(item.children?.length);

  const [expanded, setExpanded] = useState(() => hasActiveChild || isSelected);

  // Автоматически раскрываем раздел, в котором находится активный пункт
  useEffect(() => {
    if (hasActiveChild) {
      setExpanded(true);
    }
  }, [hasActiveChild]);

  // На мобильном раздел раскрывается по нажатию на иконку рельса
  useEffect(() => {
    if (forceExpand) {
      setExpanded(true);
    }
  }, [forceExpand]);

  const handleClick = () => {
    if (hasChildren) {
      setExpanded((prev) => !prev);
    } else {
      onSelect(item.id);
    }
  };

  const primary = theme.palette.primary.main;
  const activeColor = theme.palette.primary.dark;
  const textColor = theme.palette.text.primary;
  const selectedBg = alpha(primary, 0.1);
  const selectedHoverBg = alpha(primary, 0.16);

  return (
    <Box component="li" sx={{ listStyle: 'none' }}>
      <ListItemButton
        component="button"
        selected={isSelected}
        aria-current={isSelected ? 'page' : undefined}
        aria-expanded={hasChildren ? expanded : undefined}
        onClick={handleClick}
        sx={{
          minHeight: depth === 0 ? 44 : 40,
          pl: depth === 0 ? 1 : 6.5,
          pr: 1,
          py: 0.5,
          borderRadius: 1.5,
          color: isSelected ? activeColor : hasActiveChild ? activeColor : textColor,
          transition: 'background-color 150ms ease, color 150ms ease',
          [HOVER_MEDIA]: {
            '&:hover': { bgcolor: alpha(primary, 0.06) },
          },
          '&.Mui-selected': {
            bgcolor: selectedBg,
            color: activeColor,
            [HOVER_MEDIA]: {
              '&:hover': { bgcolor: selectedHoverBg },
            },
          },
          '&:focus-visible': { outline: `2px solid ${alpha(primary, 0.48)}`, outlineOffset: 1 },
          [theme.breakpoints.down('md')]: { minHeight: 48 },
          [REDUCED_MOTION]: { transition: 'none' },
        }}
      >
        {depth === 0 && item.icon && (
          <ListItemIcon
            sx={{
              width: ICON_SLOT_WIDTH,
              minWidth: ICON_SLOT_WIDTH,
              mr: 1,
              justifyContent: 'center',
              color: 'inherit',
              '& svg': { fontSize: ICON_SIZE },
            }}
          >
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
              mr: 1,
              borderRadius: '50%',
              bgcolor: isSelected ? primary : theme.palette.text.disabled,
            }}
          />
        )}
        <ListItemText
          primary={item.label}
          slotProps={{
            primary: {
              sx: {
                fontSize: depth === 0 ? TEXT_ITEM : TEXT_SUB_ITEM,
                lineHeight: 1.35,
                fontWeight: isSelected ? 600 : depth === 0 ? 500 : 400,
                [theme.breakpoints.down('md')]: { fontSize: '1rem' },
              },
            },
          }}
        />
        {hasChildren && depth === 0 && (
          <Box
            aria-hidden="true"
            sx={{
              color: 'inherit',
              opacity: 0.6,
              display: 'flex',
              alignItems: 'center',
              ml: 0.5,
              transition: 'transform 0.2s ease',
              [REDUCED_MOTION]: { transition: 'none' },
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
              p: 0,
              mt: 0.5,
              mb: 1,
              listStyle: 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 0.5,
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

// ─── Основной компонент ─────────────────────────────────────────────────────

export const SiteNavigationDrawer: React.FC<SiteNavigationDrawerProps> = ({
  activeId,
  items,
  onSelect,
  onOpenAdmin,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { refresh_data: canRefreshData, manage_settings: canManageSettings } = useAdminCapabilities();
  const isAdmin = canRefreshData || canManageSettings;

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileExpandId, setMobileExpandId] = useState<string | null>(null);

  // Развёрнутость панели на десктопе: по умолчанию подписи видны
  const [desktopExpanded, setDesktopExpanded] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    try {
      const saved = window.sessionStorage.getItem(NAV_EXPANDED_STORAGE_KEY);
      if (saved !== null) {
        return JSON.parse(saved) as boolean;
      }
    } catch {
      // Значение из storage недоступно — используем значение по умолчанию
    }
    return true;
  });

  useEffect(() => {
    if (!isMobile) {
      setMobileOpen(false);
    }
    setOpenMenuId(null);
  }, [isMobile]);

  const toggleExpanded = useCallback(() => {
    setOpenMenuId(null);
    if (isMobile) {
      setMobileOpen((prev) => !prev);
      return;
    }

    setDesktopExpanded((prev) => {
      const next = !prev;
      try {
        window.sessionStorage.setItem(NAV_EXPANDED_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Игнорируем недоступность storage
      }
      return next;
    });
  }, [isMobile]);

  const closeMobileDrawer = useCallback(() => setMobileOpen(false), []);

  const handleSelect = useCallback(
    (id: string) => {
      setOpenMenuId(null);
      if (isMobile) {
        setMobileOpen(false);
      }
      onSelect(id);
    },
    [isMobile, onSelect],
  );

  const handleRailToggleOpen = useCallback(
    (id: string) => {
      if (isMobile) {
        setMobileExpandId(id);
        setMobileOpen(true);
        return;
      }
      setOpenMenuId((prev) => (prev === id ? null : id));
    },
    [isMobile],
  );

  const primary = theme.palette.primary.main;
  const activeColor = theme.palette.primary.dark;
  const divider = theme.palette.divider;

  const panelSurfaceSx = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    '@supports (height: 100dvh)': { height: '100dvh' },
    color: theme.palette.text.primary,
    background: 'linear-gradient(180deg, rgba(235,244,255,0.95) 0%, rgba(241,247,255,0.92) 100%)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    borderRight: `1px solid ${divider}`,
    boxShadow: theme.shadows[2],
  };

  const navigationList = (
    <Box
      component="ul"
      sx={{ m: 0, p: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 0.5 }}
    >
      {items.map((item, index) => (
        <React.Fragment key={item.id}>
          {isGroupStart(items, index) && (
            <Box component="li" aria-hidden="true" sx={{ listStyle: 'none', height: 1, my: 0.5 }} />
          )}
          <ExpandedRow
            item={item}
            activeId={activeId}
            depth={0}
            onSelect={handleSelect}
            forceExpand={isMobile && mobileOpen && mobileExpandId === item.id}
          />
        </React.Fragment>
      ))}
    </Box>
  );

  const panelContent = (
    <>
      {/* Шапка: логотип, название и кнопка сворачивания */}
      <Box
        sx={{
          height: 60,
          flex: '0 0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2.5,
          borderBottom: `1px solid ${divider}`,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <Box
            sx={{
              width: ICON_SLOT_WIDTH,
              height: ICON_SLOT_WIDTH,
              flex: '0 0 auto',
              borderRadius: 1.5,
              bgcolor: alpha(primary, 0.1),
              border: `1px solid ${alpha(primary, 0.2)}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: activeColor,
            }}
          >
            <ShowChartIcon sx={{ fontSize: 16 }} />
          </Box>
          <Typography
            sx={{
              fontSize: '1rem',
              fontWeight: 700,
              color: theme.palette.text.primary,
              letterSpacing: '-0.01em',
            }}
          >
            BondsScreener
          </Typography>
        </Box>

        <IconButton
          aria-label="Панель разделов"
          aria-expanded={isMobile ? mobileOpen : desktopExpanded}
          aria-controls="site-navigation-drawer"
          onClick={toggleExpanded}
          sx={{
            width: 44,
            height: 44,
            flex: '0 0 auto',
            borderRadius: 1.5,
            color: theme.palette.text.secondary,
            bgcolor: alpha(theme.palette.background.paper, 0.7),
            border: `1px solid ${divider}`,
            [HOVER_MEDIA]: {
              '&:hover': { bgcolor: theme.palette.background.paper, color: activeColor },
            },
            [REDUCED_MOTION]: { transition: 'none' },
          }}
        >
          <ChevronLeftIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Список разделов */}
      <Box
        id="site-navigation-items"
        component="nav"
        aria-label="Разделы сайта"
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          px: 1.5,
          py: 1.5,
          scrollbarWidth: 'thin',
          scrollbarColor: `${alpha(theme.palette.text.primary, 0.28)} transparent`,
          '&::-webkit-scrollbar': { width: 6 },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: alpha(theme.palette.text.primary, 0.24),
            borderRadius: 3,
          },
          '&::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
        }}
      >
        {navigationList}
      </Box>

      {/* Карточка перехода в админ-панель */}
      {isAdmin && (
        <Box sx={{ flex: '0 0 auto', p: 1.5, borderTop: `1px solid ${divider}` }}>
          <Box
            component="button"
            type="button"
            onClick={onOpenAdmin}
            aria-label="Открыть админ-панель"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              width: '100%',
              p: 1,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.background.paper, 0.7),
              border: `1px solid ${divider}`,
              cursor: 'pointer',
              textAlign: 'left',
              fontFamily: 'inherit',
              color: theme.palette.text.primary,
              transition: 'background-color 150ms ease, border-color 150ms ease',
              [HOVER_MEDIA]: {
                '&:hover': { bgcolor: theme.palette.background.paper, borderColor: alpha(primary, 0.4) },
              },
              [REDUCED_MOTION]: { transition: 'none' },
            }}
          >
            <Box
              sx={{
                width: ICON_SLOT_WIDTH,
                height: ICON_SLOT_WIDTH,
                borderRadius: 1.5,
                bgcolor: primary,
                color: theme.palette.primary.contrastText,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <AdminPanelSettingsOutlinedIcon sx={{ fontSize: 16 }} />
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography
                noWrap
                sx={{
                  fontSize: TEXT_SUB_ITEM,
                  fontWeight: 600,
                  color: theme.palette.text.primary,
                  lineHeight: 1.2,
                }}
              >
                Админ-панель
              </Typography>
              <Typography
                noWrap
                sx={{
                  fontSize: TEXT_META,
                  color: theme.palette.text.secondary,
                  lineHeight: 1.2,
                  mt: 0.25,
                }}
              >
                Управление сервисом
              </Typography>
            </Box>
          </Box>
        </Box>
      )}
    </>
  );

  const railHidden = !isMobile && desktopExpanded;

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
        width: isMobile ? RAIL_WIDTH : desktopExpanded ? PANEL_WIDTH : RAIL_WIDTH,
        height: '100vh',
        '@supports (height: 100dvh)': { height: '100dvh' },
        overflow: 'visible',
        transition: `width ${TRANSITION_DURATION}ms ${EASING}`,
        [REDUCED_MOTION]: { transition: 'none' },
      }}
    >
      {/* Панель с подписями для десктопа */}
      {!isMobile && (
        <Box
          aria-hidden={!desktopExpanded}
          sx={{
            ...panelSurfaceSx,
            position: 'absolute',
            top: 0,
            left: 0,
            width: PANEL_WIDTH,
            opacity: desktopExpanded ? 1 : 0,
            transform: desktopExpanded ? 'translateX(0)' : 'translateX(-24px)',
            pointerEvents: desktopExpanded ? 'auto' : 'none',
            visibility: desktopExpanded ? 'visible' : 'hidden',
            transition: [
              `opacity ${TRANSITION_DURATION}ms ${EASING}`,
              `transform ${TRANSITION_DURATION}ms ${EASING}`,
              `visibility 0ms ${desktopExpanded ? '0ms' : `${TRANSITION_DURATION}ms`}`,
            ].join(', '),
            [REDUCED_MOTION]: { transition: 'none' },
          }}
        >
          {panelContent}
        </Box>
      )}

      {/* Свёрнутый рельс: остаётся точкой входа на мобильном */}
      <Box
        aria-hidden={railHidden}
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          display: 'flex',
          flexDirection: 'column',
          width: RAIL_WIDTH,
          height: '100vh',
          '@supports (height: 100dvh)': { height: '100dvh' },
          color: theme.palette.text.primary,
          background: 'linear-gradient(180deg, rgba(235,244,255,0.95) 0%, rgba(241,247,255,0.92) 100%)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRight: `1px solid ${divider}`,
          boxShadow: theme.shadows[2],
          opacity: railHidden ? 0 : 1,
          pointerEvents: railHidden ? 'none' : 'auto',
          visibility: railHidden ? 'hidden' : 'visible',
          transition: [
            `opacity ${TRANSITION_DURATION}ms ${EASING}`,
            `visibility 0ms ${railHidden ? `${TRANSITION_DURATION}ms` : '0ms'}`,
          ].join(', '),
          [REDUCED_MOTION]: { transition: 'none' },
        }}
      >
        <Box
          sx={{
            height: 60,
            flex: '0 0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: `1px solid ${divider}`,
          }}
        >
          <Tooltip title="Развернуть панель" placement="right" arrow>
            <IconButton
              onClick={toggleExpanded}
              aria-label="Панель разделов"
              aria-expanded={isMobile ? mobileOpen : desktopExpanded}
              aria-controls="site-navigation-drawer"
              sx={{
                width: 44,
                height: 44,
                borderRadius: 1.5,
                color: activeColor,
                bgcolor: alpha(theme.palette.background.paper, 0.7),
                border: `1px solid ${divider}`,
                [HOVER_MEDIA]: {
                  '&:hover': { bgcolor: theme.palette.background.paper },
                },
                [REDUCED_MOTION]: { transition: 'none' },
              }}
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

        <Box
          component="nav"
          aria-label="Разделы сайта"
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'visible',
            px: 0.5,
            py: 1.5,
            scrollbarWidth: 'none',
            '&::-webkit-scrollbar': { display: 'none' },
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
          }}
        >
          {items.map((item, index) => (
            <React.Fragment key={item.id}>
              {isGroupStart(items, index) && <Box aria-hidden="true" sx={{ height: 8 }} />}
              <CollapsedRow
                item={item}
                activeId={activeId}
                isOpen={openMenuId === item.id}
                isMobile={isMobile}
                onToggleOpen={() => handleRailToggleOpen(item.id)}
                onClose={() => setOpenMenuId(null)}
                onSelect={handleSelect}
              />
            </React.Fragment>
          ))}
        </Box>

        {isAdmin && (
          <Box
            sx={{
              flex: '0 0 auto',
              py: 1.5,
              borderTop: `1px solid ${divider}`,
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <Tooltip title="Админ-панель" placement="right" arrow>
              <IconButton
                onClick={onOpenAdmin}
                aria-label="Открыть админ-панель"
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 1.5,
                  bgcolor: alpha(primary, 0.1),
                  border: `1px solid ${alpha(primary, 0.2)}`,
                  color: activeColor,
                  [HOVER_MEDIA]: { '&:hover': { bgcolor: alpha(primary, 0.16) } },
                  [REDUCED_MOTION]: { transition: 'none' },
                }}
              >
                <AdminPanelSettingsOutlinedIcon sx={{ fontSize: ICON_SIZE }} />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Box>

      {/* Мобильная панель: оверлей поверх страницы, закрывается по выбору и Escape */}
      {isMobile && (
        <Drawer
          open={mobileOpen}
          onClose={closeMobileDrawer}
          anchor="left"
          slotProps={{
            paper: {
              sx: {
                ...panelSurfaceSx,
                width: MOBILE_PANEL_WIDTH,
                maxWidth: '86vw',
              },
            },
          }}
        >
          {panelContent}
        </Drawer>
      )}
    </Box>
  );
};
