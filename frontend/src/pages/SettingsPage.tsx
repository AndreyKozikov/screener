import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  IconButton,
  MenuItem,
  Select,
  Switch,
  Tab,
  Tabs,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import SettingsIcon from '@mui/icons-material/Settings';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import SyncIcon from '@mui/icons-material/Sync';
import QuestionAnswerIcon from '@mui/icons-material/QuestionAnswer';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { SiteNavigationDrawer } from '../components/common/SiteNavigationDrawer';
import {
  getSiteNavigationItems,
  isPortfolioNavigationId,
  resolveSiteNavigationTarget,
  writeSavedHomePageView,
} from '../utils/siteNavigation';
import { isAuthenticated, PORTFOLIO_AUTH_REDIRECT_STATE } from '../utils/auth';
import { useAdminCapabilities } from '../contexts/adminCapabilitiesContext';
import { useSettingsStore } from '../stores/settingsStore';
import type { AppSettings } from '../types/settings';
import { DEFAULT_SETTINGS } from '../types/settings';
import {
  fetchSettings,
  updateSettings,
  type SettingsField,
  type SettingsGroup,
  type SettingsSchema,
} from '../api/settings';

// Читаемый «вторичный» цвет вместо text.secondary (#757575) на светлом фоне
const MUTED_TEXT = '#4A5A72';

// ── Option lists (фронтенд-настройки моделей анализа) ─────────────────────────

const BOND_CHAT_MODELS = [
  { id: 'Автоматический выбор доступной модели', label: 'Автоматический выбор доступной модели' },
  { id: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
  { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
  { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
  { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro Preview' },
  { id: 'openrouter/deepseek-v4-pro', label: 'DeepSeek v4 Pro (OpenRouter)' },
];

const EMBEDDING_MODELS = [
  { id: 'local', label: 'Локальная BGE-M3' },
  { id: 'openrouter-bge-m3', label: 'BGE-M3 (OpenRouter)' },
];

const FLOATERS_PROVIDERS = [
  { id: 'gemini', label: 'Google Gemini 2.5 Flash Lite' },
  { id: 'gemini-flash', label: 'Google Gemini 2.5 Flash' },
  { id: 'gemini-2.5-pro', label: 'Google Gemini 2.5 Pro' },
  { id: 'gemini-2-flash', label: 'Google Gemini 2 Flash' },
  { id: 'gemini-3-flash', label: 'Google Gemini 3 Flash' },
  { id: 'gemini-3.1-pro', label: 'Google Gemini 3.1 Pro' },
  { id: 'openai-gpt-5.1', label: 'OpenAI GPT-5.1' },
  { id: 'openrouter', label: 'OpenRouter: Gemini 2.5 Flash Lite' },
  { id: 'local', label: 'Локальная модель (Qwen3-4B)' },
];

const FLOAT_PIPELINE_PROVIDERS = [
  { id: 'gemini-3-flash', label: 'Google Gemini 3 Flash' },
  { id: 'gemini', label: 'Google Gemini 2.5 Flash Lite' },
  { id: 'gemini-flash', label: 'Google Gemini 2.5 Flash' },
  { id: 'gemini-2.5-pro', label: 'Google Gemini 2.5 Pro' },
  { id: 'openai-gpt-5.1', label: 'OpenAI GPT-5.1' },
  { id: 'openrouter', label: 'OpenRouter: Gemini 2.5 Flash Lite' },
  { id: 'local', label: 'Локальная модель (Qwen3-4B)' },
];

// ── Секция (фронтенд-вкладка «Модели анализа») ───────────────────────────────

interface SectionHeaderProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  accentColor: string;
  description: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ icon, title, subtitle, accentColor, description }) => (
  <Box sx={{ mb: 2 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: '10px',
          bgcolor: `${accentColor}18`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: accentColor,
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Typography variant="body1" fontWeight={600} sx={{ lineHeight: 1.3 }}>
          {title}
        </Typography>
        <Typography variant="caption" color={MUTED_TEXT} sx={{ display: 'block', lineHeight: 1.2 }}>
          {subtitle}
        </Typography>
      </Box>
    </Box>
    <Typography
      variant="caption"
      color={MUTED_TEXT}
      sx={{ display: 'block', fontSize: '0.78rem', lineHeight: 1.55, pl: 0.5, mt: 0.5, maxWidth: 720 }}
    >
      {description}
    </Typography>
  </Box>
);

interface FrontendFieldProps {
  label: string;
  description: string;
  value: string;
  options: Array<{ id: string; label: string }>;
  defaultValue: string;
  onChange: (value: string) => void;
}

const FrontendField: React.FC<FrontendFieldProps> = ({ label, description, value, options, defaultValue, onChange }) => {
  const isDefault = value === defaultValue;
  const handleChange = (e: SelectChangeEvent<string>) => onChange(e.target.value);
  return (
    <Box sx={{ mb: 2.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.4 }}>
        <Typography variant="body2" color="text.primary" fontWeight={600}>
          {label}
        </Typography>
        {isDefault && (
          <Chip label="По умолчанию" size="small" sx={{ height: 18, fontSize: '0.65rem', bgcolor: 'action.selected', color: 'text.secondary' }} />
        )}
      </Box>
      <Typography variant="caption" color={MUTED_TEXT} sx={{ display: 'block', fontSize: '0.78rem', lineHeight: 1.45, mb: 1, maxWidth: 640 }}>
        {description}
      </Typography>
      <FormControl fullWidth size="small">
        <Select value={value} onChange={handleChange}>
          {options.map((opt) => (
            <MenuItem key={opt.id} value={opt.id}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
};

// ── Поле бэкенд-настройки (рендер по типу) ────────────────────────────────────

interface BackendFieldProps {
  field: SettingsField;
  value: unknown;
  onChange: (value: unknown) => void;
}

const BackendField: React.FC<BackendFieldProps> = ({ field, value, onChange }) => {
  const label = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.4, flexWrap: 'wrap', gap: 0.5 }}>
      <Typography variant="body2" color="text.primary" fontWeight={600}>
        {field.label}
      </Typography>
      {field.restart && (
        <Chip label="Применяется после перезапуска" size="small" sx={{ height: 18, fontSize: '0.62rem', bgcolor: 'warning.light', color: 'warning.contrastText' }} />
      )}
    </Box>
  );

  const description = (
    <Typography variant="caption" color={MUTED_TEXT} sx={{ display: 'block', fontSize: '0.78rem', lineHeight: 1.45, mb: 1, maxWidth: 640 }}>
      {field.description}
    </Typography>
  );

  // Логическое значение — отдельная карточка-переключатель
  if (field.type === 'boolean') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, p: 1.5, borderRadius: 2, bgcolor: 'rgba(25,118,210,0.045)', border: '1px solid rgba(25,118,210,0.14)', mb: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          {label}
          <Typography variant="caption" color={MUTED_TEXT} sx={{ display: 'block', fontSize: '0.78rem', lineHeight: 1.45, maxWidth: 640 }}>
            {field.description}
          </Typography>
        </Box>
        <Switch checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
      </Box>
    );
  }

  // Секрет — парольное поле, пустое значение = «не менять»
  if (field.type === 'secret') {
    return (
      <Box sx={{ mb: 2.5 }}>
        {label}
        {description}
        <TextField
          fullWidth
          size="small"
          type="password"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.is_set ? 'Ключ установлен (оставьте пустым, чтобы не менять)' : 'Ключ не задан'}
          helperText="Введите новый ключ, чтобы заменить текущий. Оставьте поле пустым — значение не изменится."
        />
      </Box>
    );
  }

  // Мультивыбор — чекбоксы в порядке списка (порядок важен для AUTO-перебора)
  if (field.type === 'multiselect') {
    const selected = Array.isArray(value) ? value.map(String) : [];
    const options = field.options ?? [];
    const toggle = (optionValue: string) => {
      const next = selected.includes(optionValue)
        ? selected.filter((v) => v !== optionValue)
        : [...selected, optionValue];
      // Сохраняем порядок опций списка, чтобы не ломать очерёдность AUTO-перебора
      onChange(options.map((o) => o.value).filter((v) => next.includes(v)));
    };
    return (
      <Box sx={{ mb: 2.5 }}>
        {label}
        {description}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4, mt: 0.5 }}>
          {options.map((opt) => (
            <FormControlLabel
              key={opt.value}
              control={<Checkbox size="small" checked={selected.includes(opt.value)} onChange={() => toggle(opt.value)} />}
              label={<Typography variant="body2">{opt.label}</Typography>}
            />
          ))}
        </Box>
      </Box>
    );
  }

  // Выпадающий список
  if (field.type === 'select') {
    const options = field.options ?? [];
    const handleChange = (e: SelectChangeEvent<string>) => onChange(e.target.value);
    return (
      <Box sx={{ mb: 2.5 }}>
        {label}
        {description}
        <FormControl fullWidth size="small">
          <Select value={String(value ?? '')} onChange={handleChange}>
            {options.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
    );
  }

  // Числа и текст
  const isNumber = field.type === 'integer' || field.type === 'number';
  return (
    <Box sx={{ mb: 2.5 }}>
      {label}
      {description}
      <TextField
        fullWidth
        size="small"
        type={isNumber ? 'number' : 'text'}
        slotProps={isNumber ? {
          htmlInput: {
            min: field.minimum ?? undefined,
            max: field.maximum ?? undefined,
            step: field.type === 'integer' ? 1 : 'any',
          },
        } : undefined}
        value={String(value ?? '')}
        onChange={(e) => {
          if (isNumber) {
            onChange(e.target.value === '' ? '' : e.target.value);
          } else {
            onChange(e.target.value);
          }
        }}
        helperText={isNumber
          ? `Значение по умолчанию: ${String(field.default ?? '')}${field.minimum != null && field.maximum != null ? `. Диапазон: ${field.minimum}–${field.maximum}` : ''}`
          : undefined}
      />
    </Box>
  );
};

// ── Вкладки ───────────────────────────────────────────────────────────────────

const BACKEND_TAB_GROUPS = ['agent', 'providers', 'local', 'services', 'keys', 'macro_dashboard'];

// ── Страница ──────────────────────────────────────────────────────────────────

/**
 * Страница настроек приложения, реализованная в виде вкладок.
 *
 * Вкладка «Модели анализа» — настройки фронтенда (localStorage): какие LLM
 * используются для чата по выпуску и флоатеров.
 * Остальные вкладки — runtime-настройки бэкенда из конфигурационных файлов
 * (config/settings.py, config/config_llm.toml): они сохраняются на сервере
 * через PUT /api/settings и применяются без правки кода.
 */
export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { manage_settings: canManageSettings } = useAdminCapabilities();

  if (!canManageSettings) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2, px: 3, textAlign: 'center' }}>
        <Typography variant="h5" fontWeight={700} color="#29476F">Доступ ограничен</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
          Раздел «Настройки» доступен только администратору.
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')} sx={{ borderRadius: '10px', px: 3 }}>
          На главную
        </Button>
      </Box>
    );
  }

  return <SettingsPageContent />;
};

const SettingsPageContent: React.FC = () => {
  const navigate = useNavigate();
  const { settings, updateSettings: updateFrontendSettings } = useSettingsStore();

  // Вкладка
  const [tab, setTab] = useState(0);

  // Бэкенд-настройки
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [backendLoading, setBackendLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [backendDraft, setBackendDraft] = useState<Record<string, unknown>>({});
  const [originalValues, setOriginalValues] = useState<Record<string, unknown>>({});

  // Фронтенд-настройки (черновик)
  const [frontendDraft, setFrontendDraft] = useState<AppSettings>({ ...settings });

  // Статус сохранения
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const savedTimer = useRef<number | null>(null);

  useEffect(() => {
    setFrontendDraft({ ...settings });
  }, [settings]);

  useEffect(() => () => {
    if (savedTimer.current) window.clearTimeout(savedTimer.current);
  }, []);

  const rebuildDraft = useCallback((next: SettingsSchema) => {
    const draft: Record<string, unknown> = {};
    const originals: Record<string, unknown> = {};
    for (const group of next.groups) {
      for (const field of group.fields) {
        originals[field.key] = field.secret ? '' : field.value;
        draft[field.key] = field.secret ? '' : field.value;
      }
    }
    setBackendDraft(draft);
    setOriginalValues(originals);
  }, []);

  const loadBackendSettings = useCallback(async () => {
    setBackendLoading(true);
    setBackendError(null);
    try {
      const data = await fetchSettings();
      setSchema(data);
      rebuildDraft(data);
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Не удалось загрузить настройки бэкенда');
    } finally {
      setBackendLoading(false);
    }
  }, [rebuildDraft]);

  useEffect(() => {
    loadBackendSettings();
  }, [loadBackendSettings]);

  const backendFields = useMemo((): Map<string, SettingsField> => {
    const byKey = new Map<string, SettingsField>();
    if (schema) {
      for (const group of schema.groups) {
        for (const field of group.fields) byKey.set(field.key, field);
      }
    }
    return byKey;
  }, [schema]);

  const backendGroup = (groupId: string): SettingsGroup | null =>
    schema?.groups.find((g) => g.id === groupId) ?? null;

  const handleBackendChange = (key: string) => (value: unknown) => {
    setBackendDraft((prev) => ({ ...prev, [key]: value }));
  };

  const handleFrontendChange = <K extends keyof AppSettings>(key: K) => (value: string) => {
    setFrontendDraft((prev) => ({ ...prev, [key]: value }));
  };

  const backendHasChanges = useMemo(() => {
    if (!schema) return false;
    for (const key of Object.keys(backendDraft)) {
      const field = backendFields.get(key);
      if (!field) continue;
      if (field.secret) {
        if (String(backendDraft[key] ?? '').trim() !== '') return true;
        continue;
      }
      if (JSON.stringify(backendDraft[key]) !== JSON.stringify(originalValues[key])) return true;
    }
    return false;
  }, [backendDraft, originalValues, backendFields, schema]);

  const frontendHasChanges = JSON.stringify(frontendDraft) !== JSON.stringify(settings);

  const hasChanges = backendHasChanges || frontendHasChanges;

  const flashSaved = () => {
    setSaved(true);
    if (savedTimer.current) window.clearTimeout(savedTimer.current);
    savedTimer.current = window.setTimeout(() => setSaved(false), 2500);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      updateFrontendSettings(frontendDraft);
      if (schema && backendHasChanges) {
        const updates: Record<string, unknown> = {};
        for (const key of Object.keys(backendDraft)) {
          const field = backendFields.get(key);
          if (!field) continue;
          if (field.secret) {
            const raw = String(backendDraft[key] ?? '').trim();
            if (raw !== '') updates[key] = raw;
            continue;
          }
          if (JSON.stringify(backendDraft[key]) !== JSON.stringify(originalValues[key])) {
            updates[key] = backendDraft[key];
          }
        }
        const next = await updateSettings(updates);
        setSchema(next);
        rebuildDraft(next);
      }
      flashSaved();
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Не удалось сохранить настройки');
    } finally {
      setSaving(false);
    }
  };

  const handleResetAll = async () => {
    setSaving(true);
    try {
      updateFrontendSettings({ ...DEFAULT_SETTINGS });
      setFrontendDraft({ ...DEFAULT_SETTINGS });
      if (schema) {
        const next = await updateSettings({}, true);
        setSchema(next);
        rebuildDraft(next);
      }
      flashSaved();
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Не удалось сбросить настройки');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setFrontendDraft({ ...settings });
    if (schema) rebuildDraft(schema);
  };

  const handleSiteNavigationSelect = (id: string) => {
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

  const renderBackendTab = (groupId: string) => {
    const group = backendGroup(groupId);
    if (!group) return null;
    return (
      <Box>
        <Typography
          variant="caption"
          color={MUTED_TEXT}
          sx={{ display: 'block', fontSize: '0.8rem', lineHeight: 1.6, mb: 2, maxWidth: 760 }}
        >
          {group.description}
        </Typography>
        {groupId === 'macro_dashboard'
          ? [...new Set(group.fields.map((field) => field.section ?? 'Параметры'))].map((section) => (
            <Box key={section} sx={{ mb: 2.5 }}>
              <Typography variant="subtitle2" sx={{ color: '#29476F', fontWeight: 700, mb: 1 }}>
                {section}
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' }, columnGap: 2.5 }}>
                {group.fields.filter((field) => (field.section ?? 'Параметры') === section).map((field) => (
                  <BackendField
                    key={field.key}
                    field={field}
                    value={backendDraft[field.key]}
                    onChange={handleBackendChange(field.key)}
                  />
                ))}
              </Box>
            </Box>
          ))
          : group.fields.map((field) => (
            <BackendField
              key={field.key}
              field={field}
              value={backendDraft[field.key]}
              onChange={handleBackendChange(field.key)}
            />
          ))}
      </Box>
    );
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
        activeId="settings"
        items={getSiteNavigationItems(isAuthenticated())}
        onSelect={handleSiteNavigationSelect}
        onOpenSettings={() => navigate('/settings')}
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
                  Настройки BondsScreener
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
          width: '100%',
          px: { xs: 1.25, md: 3.5, xl: 4.5 },
          py: { xs: 1.25, md: 2.5 },
        }}>
          <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
            <Box
              sx={{
                bgcolor: 'rgba(255,255,255,0.82)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                borderRadius: '20px',
                border: '1px solid #E2E8F0',
                boxShadow: '0 8px 32px rgba(29,61,103,0.08), 0 2px 8px rgba(29,61,103,0.04)',
                overflow: 'hidden',
              }}
            >
              {/* ── Title ── */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  px: 3,
                  py: 2,
                  borderBottom: '1px solid #E2E8F0',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box
                    sx={{
                      width: 40,
                      height: 40,
                      borderRadius: '12px',
                      bgcolor: 'primary.main',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'white',
                    }}
                  >
                    <SettingsIcon sx={{ fontSize: 22 }} />
                  </Box>
                  <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <Typography variant="body1" fontWeight={700} sx={{ lineHeight: 1.3 }}>
                      Настройки
                    </Typography>
<Typography variant="caption" color={MUTED_TEXT} sx={{ display: 'block', lineHeight: 1.2 }}>
                    Параметры моделей, агента, внешних сервисов и макродашборда
                  </Typography>
                  </Box>
                </Box>
                <Tooltip title="Сбросить все настройки к значениям по умолчанию">
                  <span>
                    <IconButton size="small" onClick={handleResetAll} disabled={saving || backendLoading} sx={{ color: 'text.secondary' }}>
                      <RestartAltIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>

              {/* ── Tabs ── */}
              <Box sx={{ borderBottom: '1px solid #E2E8F0' }}>
                <Tabs
                  value={tab}
                  onChange={(_, v) => setTab(v)}
                  variant="scrollable"
                  scrollButtons="auto"
                  allowScrollButtonsMobile
                  sx={{
                    px: 1.5,
                    '& .MuiTab-root': { textTransform: 'none', fontSize: '0.85rem', fontWeight: 600, minHeight: 46 },
                  }}
                >
                  <Tab label="Модели анализа" />
                  <Tab label="ИИ-агент" />
                  <Tab label="Провайдеры LLM" />
                  <Tab label="Локальная LLM" />
                  <Tab label="Внешние сервисы" />
                  <Tab label="Ключи API" />
                  <Tab label="Макродашборд" />
                </Tabs>
              </Box>

              {/* ── Content ── */}
              <Box sx={{ px: 3, py: 2.5 }}>
                {backendError && (
                  <Alert
                    severity="error"
                    sx={{ mb: 2, borderRadius: 2 }}
                    action={
                      <Button size="small" color="inherit" onClick={loadBackendSettings}>
                        Повторить
                      </Button>
                    }
                  >
                    {backendError}
                  </Alert>
                )}

                {/* Вкладка 0: фронтенд-настройки моделей */}
                {tab === 0 && (
                  <Box>
                    <Typography
                      variant="caption"
                      color={MUTED_TEXT}
                      sx={{ display: 'block', fontSize: '0.8rem', lineHeight: 1.65, mb: 2, maxWidth: 760 }}
                    >
                      Настройки языковых моделей, которые фронтенд передаёт на сервер при каждом запросе.
                      Сохраняются в браузере (localStorage) и применяются сразу.
                    </Typography>

                    <SectionHeader
                      icon={<QuestionAnswerIcon sx={{ fontSize: 20 }} />}
                      title="Чат с ИИ по облигации"
                      subtitle="Детали облигации → Чат с ИИ (Vector Retrieval)"
                      accentColor="#7b1fa2"
                      description="Настройки чата на карточке облигации. Чат отвечает на вопросы по выпуску через векторный поиск по раскрытию эмитента (eDisclosure)."
                    />
                    <FrontendField
                      label="Языковая модель"
                      description="Генерирует ответы чата по найденным фрагментам раскрытия. «Автоматический выбор» позволяет серверу подобрать модель самостоятельно."
                      value={frontendDraft.bondChatModel}
                      options={BOND_CHAT_MODELS}
                      defaultValue={DEFAULT_SETTINGS.bondChatModel}
                      onChange={handleFrontendChange('bondChatModel')}
                    />
                    <FrontendField
                      label="Модель эмбеддингов"
                      description="Преобразует тексты раскрытия в векторы для семантического поиска. Локальная BGE-M3 не передаёт данные наружу; OpenRouter — внешний сервис."
                      value={frontendDraft.bondChatEmbeddingModel}
                      options={EMBEDDING_MODELS}
                      defaultValue={DEFAULT_SETTINGS.bondChatEmbeddingModel}
                      onChange={handleFrontendChange('bondChatEmbeddingModel')}
                    />

                    <Divider sx={{ my: 2.5 }} />

                    <SectionHeader
                      icon={<SyncIcon sx={{ fontSize: 20 }} />}
                      title="Обновление данных — Флоатеры"
                      subtitle="Кнопка обновления → Флоатеры (eDisclosure)"
                      accentColor="#2e7d32"
                      description="Настройки процесса обновления параметров флоатеров (облигаций с плавающим купоном) по данным eDisclosure при нажатии «Обновить»."
                    />
                    <FrontendField
                      label="AI-провайдер для флоатеров"
                      description="Какая языковая модель извлекает купонные ставки и условия флоатеров из свежих раскрытий эмитента при массовом обновлении данных."
                      value={frontendDraft.floatersProvider}
                      options={FLOATERS_PROVIDERS}
                      defaultValue={DEFAULT_SETTINGS.floatersProvider}
                      onChange={handleFrontendChange('floatersProvider')}
                    />

                    <Divider sx={{ my: 2.5 }} />

                    <SectionHeader
                      icon={<PsychologyIcon sx={{ fontSize: 20 }} />}
                      title="LLM Pipeline — Параметры флоатера"
                      subtitle="Детали облигации → Обновить параметры"
                      accentColor="#e65100"
                      description="Конвейер пересчёта параметров конкретного флоатера на его карточке: извлечение данных из раскрытия, расчёт ставки, проверка и запись результата."
                    />
                    <FrontendField
                      label="Провайдер LLM"
                      description="Модель, выполняющая все шаги конвейера расчёта параметров флоатера для одного выпуска."
                      value={frontendDraft.floatPipelineProvider}
                      options={FLOAT_PIPELINE_PROVIDERS}
                      defaultValue={DEFAULT_SETTINGS.floatPipelineProvider}
                      onChange={handleFrontendChange('floatPipelineProvider')}
                    />
                    <FrontendField
                      label="Модель эмбеддингов"
                      description="Векторная модель для поиска нужных фрагментов в документах эмитента в рамках конвейера расчёта параметров флоатера."
                      value={frontendDraft.floatPipelineEmbeddingModel}
                      options={EMBEDDING_MODELS}
                      defaultValue={DEFAULT_SETTINGS.floatPipelineEmbeddingModel}
                      onChange={handleFrontendChange('floatPipelineEmbeddingModel')}
                    />
                  </Box>
                )}

                {/* Вкладки бэкенд-настроек */}
                {tab >= 1 && tab <= 6 && (
                  backendLoading ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5, py: 6 }}>
                      <CircularProgress size={28} />
                      <Typography variant="body2" color="text.secondary">Загрузка настроек сервера…</Typography>
                    </Box>
                  ) : (
                    renderBackendTab(BACKEND_TAB_GROUPS[tab - 1])
                  )
                )}
              </Box>

              {/* ── Actions ── */}
              <Box
                sx={{
                  px: 3,
                  py: 2,
                  borderTop: '1px solid #E2E8F0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: 1,
                  flexWrap: 'wrap',
                }}
              >
                {saved && (
                  <Chip label="Настройки сохранены" color="success" size="small" sx={{ mr: 'auto', fontWeight: 500 }} />
                )}
                {saving && <CircularProgress size={18} sx={{ mr: 'auto' }} />}
                <Button onClick={handleCancel} color="inherit" disabled={saving}>
                  Отмена
                </Button>
                <Button
                  onClick={handleSave}
                  variant="contained"
                  disabled={!hasChanges || saving || backendLoading}
                  disableElevation
                  sx={{ borderRadius: '10px', px: 3 }}
                >
                  Сохранить изменения
                </Button>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SettingsPage;
