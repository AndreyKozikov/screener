import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Select,
  MenuItem,
  FormControl,
  Divider,
  Tooltip,
  IconButton,
  Chip,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import SettingsIcon from '@mui/icons-material/Settings';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import QuestionAnswerIcon from '@mui/icons-material/QuestionAnswer';
import SyncIcon from '@mui/icons-material/Sync';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { useSettingsStore } from '../../stores/settingsStore';
import type { AppSettings } from '../../types/settings';
import { DEFAULT_SETTINGS } from '../../types/settings';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

// ── Option lists ──────────────────────────────────────────────────────────────

const GPT_MODELS = [
  { id: 'gpt-5.1', label: 'GPT-5.1' },
  { id: 'gpt-4o', label: 'GPT-4o' },
  { id: 'gpt-4o-mini', label: 'GPT-4o Mini' },
];

const QWEN_MODELS = [
  { id: 'qwen/qwen3-235b-a22b:free', label: 'Qwen3 235B A22B (Free)' },
  { id: 'qwen/qwen3-30b-a3b:free', label: 'Qwen3 30B A3B (Free)' },
  { id: 'qwen/qwen-2.5-72b-instruct:free', label: 'Qwen 2.5 72B Instruct (Free)' },
];

const GROK_MODELS = [
  { id: 'x-ai/grok-4.1-fast:free', label: 'Grok 4.1 Fast (Free)' },
  { id: 'x-ai/grok-4.1:free', label: 'Grok 4.1 (Free)' },
  { id: 'x-ai/grok-3-mini-beta', label: 'Grok 3 Mini Beta' },
];

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

// ── Section Header component ──────────────────────────────────────────────────

interface SectionHeaderProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  accentColor: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ icon, title, subtitle, accentColor }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
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
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.2 }}>
        {subtitle}
      </Typography>
    </Box>
  </Box>
);

// ── Field component ───────────────────────────────────────────────────────────

interface SettingSelectProps {
  label: string;
  value: string;
  options: Array<{ id: string; label: string }>;
  defaultValue: string;
  onChange: (value: string) => void;
}

const SettingSelect: React.FC<SettingSelectProps> = ({ label, value, options, defaultValue, onChange }) => {
  const isDefault = value === defaultValue;

  const handleChange = (e: SelectChangeEvent<string>) => {
    onChange(e.target.value);
  };

  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
        <Typography variant="body2" color="text.secondary" fontWeight={500}>
          {label}
        </Typography>
        {isDefault && (
          <Chip
            label="По умолчанию"
            size="small"
            sx={{
              height: 18,
              fontSize: '0.65rem',
              bgcolor: 'action.selected',
              color: 'text.secondary',
            }}
          />
        )}
      </Box>
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

// ── Main Dialog ───────────────────────────────────────────────────────────────

/**
 * SettingsDialog
 *
 * Global settings panel allowing the user to configure API parameters
 * for all major endpoints, grouped by site section.
 */
export const SettingsDialog: React.FC<SettingsDialogProps> = ({ open, onClose }) => {
  const { settings, updateSettings } = useSettingsStore();
  const [draft, setDraft] = useState<AppSettings>({ ...settings });

  // Sync draft when dialog opens
  useEffect(() => {
    if (open) {
      setDraft({ ...settings });
    }
  }, [open, settings]);

  const handleChange = <K extends keyof AppSettings>(key: K) =>
    (value: string) => {
      setDraft((prev) => ({ ...prev, [key]: value }));
    };

  const handleSave = () => {
    updateSettings(draft);
    onClose();
  };

  const handleReset = () => {
    setDraft({ ...DEFAULT_SETTINGS });
  };

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(settings);
  const hasDraftDiff = JSON.stringify(draft) !== JSON.stringify(DEFAULT_SETTINGS);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="settings-dialog-title"
      PaperProps={{
        sx: {
          borderRadius: '20px',
          border: '1px solid #E2E8F0',
          maxHeight: '90vh',
        },
      }}
    >
      {/* ── Title ── */}
      <DialogTitle
        id="settings-dialog-title"
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
          borderBottom: '1px solid #E2E8F0',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              bgcolor: 'primary.main',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            <SettingsIcon sx={{ fontSize: 20 }} />
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <Typography variant="body1" fontWeight={700} sx={{ lineHeight: 1.3 }}>
              Настройки
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.2 }}>
              Глобальные параметры API-запросов
            </Typography>
          </Box>
        </Box>
        <Tooltip title="Сбросить все к умолчаниям">
          <span>
            <IconButton
              size="small"
              onClick={handleReset}
              disabled={!hasDraftDiff}
              sx={{ color: 'text.secondary' }}
            >
              <RestartAltIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </DialogTitle>

      {/* ── Content ── */}
      <DialogContent sx={{ py: 3, px: 3 }}>
        {/* ── Section 1: LLM Analysis ── */}
        <SectionHeader
          icon={<SmartToyIcon sx={{ fontSize: 20 }} />}
          title="Анализ облигаций (AI)"
          subtitle="Скринер → Сравнение → AI-анализ"
          accentColor="#1976d2"
        />

        <SettingSelect
          label="GPT (OpenAI) — модель"
          value={draft.llmGptModel}
          options={GPT_MODELS}
          defaultValue={DEFAULT_SETTINGS.llmGptModel}
          onChange={handleChange('llmGptModel')}
        />
        <SettingSelect
          label="Qwen (OpenRouter) — модель"
          value={draft.llmQwenModel}
          options={QWEN_MODELS}
          defaultValue={DEFAULT_SETTINGS.llmQwenModel}
          onChange={handleChange('llmQwenModel')}
        />
        <SettingSelect
          label="Grok (OpenRouter) — модель"
          value={draft.llmGrokModel}
          options={GROK_MODELS}
          defaultValue={DEFAULT_SETTINGS.llmGrokModel}
          onChange={handleChange('llmGrokModel')}
        />

        <Divider sx={{ my: 2.5 }} />

        {/* ── Section 2: Bond Chat ── */}
        <SectionHeader
          icon={<QuestionAnswerIcon sx={{ fontSize: 20 }} />}
          title="Чат с ИИ по облигации"
          subtitle="Детали облигации → Чат с ИИ (Vector Retrieval)"
          accentColor="#7b1fa2"
        />

        <SettingSelect
          label="Языковая модель"
          value={draft.bondChatModel}
          options={BOND_CHAT_MODELS}
          defaultValue={DEFAULT_SETTINGS.bondChatModel}
          onChange={handleChange('bondChatModel')}
        />
        <SettingSelect
          label="Модель эмбеддингов"
          value={draft.bondChatEmbeddingModel}
          options={EMBEDDING_MODELS}
          defaultValue={DEFAULT_SETTINGS.bondChatEmbeddingModel}
          onChange={handleChange('bondChatEmbeddingModel')}
        />

        <Divider sx={{ my: 2.5 }} />

        {/* ── Section 3: Data Refresh ── */}
        <SectionHeader
          icon={<SyncIcon sx={{ fontSize: 20 }} />}
          title="Обновление данных — Флоатеры"
          subtitle="Кнопка обновления → Флоатеры (eDisclosure)"
          accentColor="#2e7d32"
        />

        <SettingSelect
          label="AI-провайдер для флоатеров"
          value={draft.floatersProvider}
          options={FLOATERS_PROVIDERS}
          defaultValue={DEFAULT_SETTINGS.floatersProvider}
          onChange={handleChange('floatersProvider')}
        />

        <Divider sx={{ my: 2.5 }} />

        {/* ── Section 4: LLM Float Pipeline ── */}
        <SectionHeader
          icon={<PsychologyIcon sx={{ fontSize: 20 }} />}
          title="LLM Pipeline — Параметры флоатера"
          subtitle="Детали облигации → Обновить параметры"
          accentColor="#e65100"
        />

        <SettingSelect
          label="Провайдер LLM"
          value={draft.floatPipelineProvider}
          options={FLOAT_PIPELINE_PROVIDERS}
          defaultValue={DEFAULT_SETTINGS.floatPipelineProvider}
          onChange={handleChange('floatPipelineProvider')}
        />
        <SettingSelect
          label="Модель эмбеддингов"
          value={draft.floatPipelineEmbeddingModel}
          options={EMBEDDING_MODELS}
          defaultValue={DEFAULT_SETTINGS.floatPipelineEmbeddingModel}
          onChange={handleChange('floatPipelineEmbeddingModel')}
        />
      </DialogContent>

      {/* ── Actions ── */}
      <DialogActions
        sx={{
          px: 3,
          py: 2,
          borderTop: '1px solid #E2E8F0',
          gap: 1,
        }}
      >
        <Button onClick={onClose} color="inherit">
          Отмена
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={!hasChanges}
          disableElevation
          sx={{ borderRadius: '10px', px: 3 }}
        >
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
};
