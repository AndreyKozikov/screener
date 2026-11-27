import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import { fetchDataUpdateRun, fetchDataUpdateStatuses, type DataUpdateRunDetail, type DataUpdateStatusItem, type DataUpdateStatusValue } from '../api/dataUpdates';
import { DATA_REFRESH_TASKS, type DataRefreshTaskDefinition } from '../config/dataRefreshTasks';
import { useAdminCapabilities } from '../contexts/adminCapabilitiesContext';
import { copyTextToClipboard } from '../utils/clipboard';

type StatusKind = DataUpdateStatusValue | 'unknown';

const STATUS_META: Record<StatusKind, { color: string; ring: string; textColor: string; label: string }> = {
  success: { color: '#2E7D32', ring: 'rgba(46,125,50,0.16)', textColor: '#1B5E20', label: 'Успешно' },
  error: { color: '#C62828', ring: 'rgba(198,40,40,0.16)', textColor: '#B42318', label: 'Ошибка' },
  running: { color: '#B26A00', ring: 'rgba(178,106,0,0.18)', textColor: '#8A5200', label: 'Выполняется' },
  unknown: { color: '#94A3B8', ring: 'rgba(148,163,184,0.18)', textColor: '#64748B', label: 'Нет данных' },
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
};

const formatDuration = (durationMs?: number | null): string | null => {
  if (durationMs == null || durationMs < 0) return null;
  const totalSeconds = Math.max(0, Math.round(durationMs / 1000));
  if (totalSeconds < 60) return `${totalSeconds} с`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return seconds ? `${minutes} мин ${seconds} с` : `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return restMinutes ? `${hours} ч ${restMinutes} мин` : `${hours} ч`;
};

const triggerLabel = (trigger?: string | null): string | null => {
  if (trigger === 'manual') return 'вручную';
  if (trigger === 'scheduled') return 'по расписанию';
  return null;
};

const statusKind = (item?: DataUpdateStatusItem | null): StatusKind =>
  item?.status === 'success' || item?.status === 'error' || item?.status === 'running'
    ? item.status
    : 'unknown';

const statusText = (item?: DataUpdateStatusItem | null): string => {
  if (!item?.status) return 'Нет данных об обновлении';
  const timestamp = formatDateTime(item.finished_at ?? item.started_at);
  if (item.status === 'success') return `Обновлено: ${timestamp}`;
  if (item.status === 'error') return `Ошибка · последняя попытка: ${timestamp}`;
  return `Выполняется с ${formatDateTime(item.started_at)}`;
};

const DataUpdateRow: FC<{
  task: DataRefreshTaskDefinition;
  item?: DataUpdateStatusItem;
  onOpenLog: (task: DataRefreshTaskDefinition, runId: string) => void;
}> = ({ task, item, onOpenLog }) => {
  const kind = statusKind(item);
  const meta = STATUS_META[kind];
  const duration = formatDuration(item?.duration_ms);
  const trigger = triggerLabel(item?.trigger);
  const hasLog = Boolean(item?.log_available && item?.run_id);
  const isRunning = kind === 'running';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: { xs: 'flex-start', sm: 'center' },
        gap: { xs: 1, sm: 2 },
        px: { xs: 1.5, sm: 2.25 },
        py: 1.75,
        borderBottom: '1px solid rgba(26,66,118,0.08)',
        flexWrap: { xs: 'wrap', sm: 'nowrap' },
        '&:last-of-type': { borderBottom: 0 },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0, flex: 1 }}>
        <Box
          sx={{
            width: 11,
            height: 11,
            borderRadius: '50%',
            bgcolor: meta.color,
            boxShadow: `0 0 0 4px ${meta.ring}`,
            flexShrink: 0,
            animation: isRunning ? 'data-update-pulse 1.6s ease-in-out infinite' : 'none',
            '@keyframes data-update-pulse': {
              '0%, 100%': { opacity: 1, transform: 'scale(1)' },
              '50%': { opacity: 0.55, transform: 'scale(0.82)' },
            },
          }}
        />
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" fontWeight={650} color="#1D3557" sx={{ lineHeight: 1.35 }}>
            {task.statusLabel}
          </Typography>
          {trigger && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.2 }}>
              {trigger}
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ textAlign: { xs: 'left', sm: 'right' }, minWidth: { sm: 230 }, flexShrink: 0 }}>
        <Typography variant="body2" fontWeight={600} sx={{ color: meta.textColor }}>
          {statusText(item)}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.2 }}>
          {item?.status === 'error'
            ? item.error_message
              ? item.error_message.length > 120
                ? `${item.error_message.slice(0, 120)}…`
                : item.error_message
              : duration
                ? `Длительность: ${duration}`
                : 'Подробности в логе'
            : duration
              ? `Длительность: ${duration}`
              : kind === 'unknown'
                ? 'Обновление ещё не запускалось'
                : ''}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', minWidth: { sm: 78 }, flexShrink: 0 }}>
        {hasLog && kind === 'error' && (
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<DescriptionOutlinedIcon fontSize="small" />}
            onClick={() => onOpenLog(task, item?.run_id as string)}
            sx={{ textTransform: 'none', whiteSpace: 'nowrap' }}
          >
            Лог
          </Button>
        )}
        {hasLog && kind === 'success' && (
          <Tooltip title="Открыть лог обновления">
            <IconButton
              size="small"
              aria-label={`Открыть лог: ${task.statusLabel}`}
              onClick={() => onOpenLog(task, item?.run_id as string)}
              sx={{ color: 'text.secondary' }}
            >
              <DescriptionOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {isRunning && !hasLog && (
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            Лог появится после завершения
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export const DataUpdatesAdminPage: FC = () => {
  const navigate = useNavigate();
  const { refresh_data: canRefreshData, manage_settings: canManageSettings } = useAdminCapabilities();
  const isAdmin = canRefreshData || canManageSettings;

  const [statuses, setStatuses] = useState<Record<string, DataUpdateStatusItem>>({});
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [logOpen, setLogOpen] = useState(false);
  const [logTask, setLogTask] = useState<DataRefreshTaskDefinition | null>(null);
  const [logRun, setLogRun] = useState<DataUpdateRunDetail | null>(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');

  const loadStatuses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDataUpdateStatuses();
      const next: Record<string, DataUpdateStatusItem> = {};
      for (const item of data.items) {
        next[item.task_id] = item;
      }
      setStatuses(next);
      setGeneratedAt(data.generated_at);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить историю обновлений');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatuses();
  }, [loadStatuses]);

  const counts = useMemo(() => {
    let success = 0;
    let failure = 0;
    let running = 0;
    let empty = 0;
    for (const task of DATA_REFRESH_TASKS) {
      const kind = statusKind(statuses[task.id]);
      if (kind === 'success') success += 1;
      else if (kind === 'error') failure += 1;
      else if (kind === 'running') running += 1;
      else empty += 1;
    }
    return { success, failure, running, empty };
  }, [statuses]);

  const hasAnyRun = useMemo(
    () => DATA_REFRESH_TASKS.some((task) => Boolean(statuses[task.id]?.status)),
    [statuses],
  );

  const openLog = useCallback(async (task: DataRefreshTaskDefinition, runId: string) => {
    setLogTask(task);
    setLogOpen(true);
    setLogRun(null);
    setLogError(null);
    setCopyState('idle');
    setLogLoading(true);
    try {
      setLogRun(await fetchDataUpdateRun(runId));
    } catch (err) {
      setLogError(err instanceof Error ? err.message : 'Не удалось загрузить лог обновления');
    } finally {
      setLogLoading(false);
    }
  }, []);

  const closeLog = useCallback(() => {
    setLogOpen(false);
    setLogRun(null);
    setLogError(null);
    setCopyState('idle');
  }, []);

  const downloadLog = useCallback(() => {
    if (!logRun?.log) return;
    const blob = new Blob([logRun.log], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `data-update-${logRun.task_id}-${logRun.run_id ?? 'log'}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [logRun]);

  const copyLog = useCallback(async () => {
    if (!logRun?.log) return;
    const copied = await copyTextToClipboard(logRun.log);
    if (copied) {
      setCopyState('copied');
      window.setTimeout(() => setCopyState('idle'), 1800);
      return;
    }
    setCopyState('failed');
  }, [logRun]);

  if (!isAdmin) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: '#F4F7FD', p: 3 }}>
        <Paper variant="outlined" sx={{ width: '100%', maxWidth: 440, p: 4, borderRadius: 3, textAlign: 'center' }}>
          <Typography variant="h5" component="h1" fontWeight={700} color="#17345B">Доступ ограничен</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            Результаты обновлений доступны только администратору.
          </Typography>
          <Button variant="contained" onClick={() => navigate('/admin')} sx={{ textTransform: 'none' }}>
            В админ-панель
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#F4F7FD', py: { xs: 1.5, md: 3 }, px: { xs: 1, md: 2.5 } }}>
      <Container maxWidth="lg" disableGutters>
        <Paper elevation={0} sx={{ p: { xs: 2, md: 2.5 }, mb: 2, borderRadius: 3, border: '1px solid rgba(26,66,118,0.1)' }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" gap={1.5}>
            <Box>
              <Typography variant="h4" component="h1" fontWeight={750} color="#17345B" sx={{ fontSize: { xs: '1.55rem', md: '2rem' } }}>
                Результаты обновления данных
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
                Статус последнего обновления по каждому пункту и лог ошибок.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} sx={{ alignSelf: { xs: 'flex-start', sm: 'auto' } }}>
              <Button
                variant="outlined"
                startIcon={<ArrowBackRoundedIcon />}
                onClick={() => navigate('/admin')}
                sx={{ textTransform: 'none' }}
              >
                Админ-панель
              </Button>
              <Button
                variant="contained"
                startIcon={<RefreshRoundedIcon />}
                onClick={() => void loadStatuses()}
                disabled={loading}
                sx={{ textTransform: 'none' }}
              >
                Обновить
              </Button>
            </Stack>
          </Stack>

          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 2 }}>
            <Chip size="small" label={`Успешно: ${counts.success}`} sx={{ bgcolor: '#EFFAF4', color: '#2E7D32', fontWeight: 650 }} />
            <Chip size="small" label={`С ошибкой: ${counts.failure}`} sx={{ bgcolor: '#FFF1F0', color: '#B42318', fontWeight: 650 }} />
            {counts.running > 0 && (
              <Chip size="small" label={`Выполняется: ${counts.running}`} sx={{ bgcolor: '#FFF7E8', color: '#8A5200', fontWeight: 650 }} />
            )}
            <Chip size="small" label={`Нет данных: ${counts.empty}`} sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 650 }} />
            {generatedAt && (
              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center', ml: { sm: 'auto' } }}>
                Проверено: {formatDateTime(generatedAt)}
              </Typography>
            )}
          </Stack>
        </Paper>

        {error && (
          <Alert
            severity="error"
            action={<Button color="inherit" size="small" onClick={() => void loadStatuses()}>Повторить</Button>}
            sx={{ mb: 2, borderRadius: 2 }}
          >
            {error}
          </Alert>
        )}

        {!hasAnyRun && !loading && !error && (
          <Alert severity="info" sx={{ mb: 2, borderRadius: 2 }}>
            История ведётся с момента включения журнала. После первого обновления здесь появятся статус, время и лог.
          </Alert>
        )}

        <Paper variant="outlined" sx={{ borderRadius: 3, borderColor: 'rgba(26,66,118,0.12)', overflow: 'hidden' }}>
          {loading && !hasAnyRun ? (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 7 }}>
              <CircularProgress size={30} />
            </Box>
          ) : (
            <Box>
              {DATA_REFRESH_TASKS.map((task) => (
                <DataUpdateRow key={task.id} task={task} item={statuses[task.id]} onOpenLog={openLog} />
              ))}
            </Box>
          )}
        </Paper>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5, px: 0.5 }}>
          Автоматические обновления по расписанию также учитываются в статусах.
        </Typography>
      </Container>

      <Dialog open={logOpen} onClose={closeLog} maxWidth="md" fullWidth scroll="paper">
        <DialogTitle sx={{ pr: 6 }}>
          <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
            <Typography component="span" variant="h6" fontWeight={700} color="#17345B">
              {logTask?.statusLabel ?? 'Лог обновления'}
            </Typography>
            {logRun && (
              <Chip
                size="small"
                label={STATUS_META[statusKind(logRun)].label}
                sx={{
                  bgcolor: STATUS_META[statusKind(logRun)].ring,
                  color: STATUS_META[statusKind(logRun)].textColor,
                  fontWeight: 650,
                }}
              />
            )}
          </Stack>
          {logRun && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {statusText(logRun)}
              {logRun.trigger ? ` · ${triggerLabel(logRun.trigger)}` : ''}
              {formatDuration(logRun.duration_ms) ? ` · ${formatDuration(logRun.duration_ms)}` : ''}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent dividers>
          {copyState === 'failed' && (
            <Alert severity="warning" sx={{ mb: 2, borderRadius: 2 }}>
              Браузер не разрешил доступ к буферу обмена. Выделите текст лога вручную и нажмите Ctrl+C.
            </Alert>
          )}
          {logLoading && (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 5 }}>
              <CircularProgress size={28} />
            </Box>
          )}
          {!logLoading && logError && (
            <Alert severity="error" sx={{ borderRadius: 2 }}>{logError}</Alert>
          )}
          {!logLoading && !logError && logRun?.error_message && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>
              {logRun.error_message}
            </Alert>
          )}
          {!logLoading && !logError && logRun?.log && (
            <Box
              component="pre"
              sx={{
                m: 0,
                p: 2,
                borderRadius: 2,
                bgcolor: '#101828',
                color: '#D7E3F4',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                fontSize: '0.78rem',
                lineHeight: 1.55,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                maxHeight: '55vh',
                overflow: 'auto',
              }}
            >
              {logRun.log}
            </Box>
          )}
          {!logLoading && !logError && !logRun?.log && (
            <Alert severity="info" sx={{ borderRadius: 2 }}>
              Лог для этого запуска недоступен.
            </Alert>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={downloadLog}
            disabled={!logRun?.log}
            startIcon={<DownloadRoundedIcon />}
            sx={{ textTransform: 'none' }}
          >
            Скачать .txt
          </Button>
          <Button
            onClick={() => void copyLog()}
            disabled={!logRun?.log}
            startIcon={copyState === 'copied' ? <CheckRoundedIcon /> : <ContentCopyRoundedIcon />}
            sx={{ textTransform: 'none' }}
          >
            {copyState === 'copied' ? 'Скопировано' : 'Копировать'}
          </Button>
          <Button onClick={closeLog} sx={{ textTransform: 'none' }}>Закрыть</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
