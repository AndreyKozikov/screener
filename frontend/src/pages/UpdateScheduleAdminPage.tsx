import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import {
  fetchUpdateSchedule,
  type UpdateScheduleItem,
  type UpdateScheduleResponse,
  type UpdateScheduleState,
} from '../api/updateSchedule';
import { DATA_REFRESH_TASKS } from '../config/dataRefreshTasks';
import { useAdminCapabilities } from '../contexts/adminCapabilitiesContext';

const STATE_META: Record<
  UpdateScheduleState,
  { label: string; color: string; ring: string; textColor: string }
> = {
  scheduled: { label: 'По расписанию', color: '#2E7D32', ring: 'rgba(46,125,50,0.16)', textColor: '#1B5E20' },
  paused: { label: 'Приостановлено', color: '#B26A00', ring: 'rgba(178,106,0,0.18)', textColor: '#8A5200' },
  disabled: { label: 'Отключено', color: '#C62828', ring: 'rgba(198,40,40,0.16)', textColor: '#B42318' },
  not_installed: { label: 'Не установлено', color: '#C62828', ring: 'rgba(198,40,40,0.16)', textColor: '#B42318' },
  unknown: { label: 'Статус неизвестен', color: '#94A3B8', ring: 'rgba(148,163,184,0.18)', textColor: '#64748B' },
};

const TASK_LABELS: Record<string, string> = Object.fromEntries(
  DATA_REFRESH_TASKS.map((task) => [task.id, task.statusLabel]),
);

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

const formatCountdown = (target: string, now: number): string | null => {
  const diffMs = new Date(target).getTime() - now;
  if (Number.isNaN(diffMs)) return null;
  if (diffMs <= 0) return 'вот-вот';

  const totalMinutes = Math.ceil(diffMs / 60_000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  const parts: string[] = [];
  if (days) parts.push(`${days} д`);
  if (hours) parts.push(`${hours} ч`);
  if (!days && minutes) parts.push(`${minutes} мин`);
  return parts.length ? `через ${parts.join(' ')}` : 'менее минуты';
};

const ScheduleRow: FC<{ item: UpdateScheduleItem; now: number }> = ({ item, now }) => {
  const meta = STATE_META[item.state] ?? STATE_META.unknown;
  const label = TASK_LABELS[item.task_id] ?? item.task_id;
  const scheduleText = item.schedule_human ?? item.schedule ?? 'Расписание не объявлено';
  const nextRun = item.next_elapse ? formatDateTime(item.next_elapse) : '—';
  const countdown = item.next_elapse ? formatCountdown(item.next_elapse, now) : null;

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
          }}
        />
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" fontWeight={650} color="#1D3557" sx={{ lineHeight: 1.35 }}>
            {label}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.2 }}>
            {scheduleText}
          </Typography>
          {item.schedule && (
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                mt: 0.2,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                color: 'rgba(71,85,105,0.8)',
                wordBreak: 'break-word',
              }}
            >
              {item.schedule} · {item.timer_unit}
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ textAlign: { xs: 'left', sm: 'right' }, minWidth: { sm: 220 }, flexShrink: 0 }}>
        <Typography variant="body2" fontWeight={600} sx={{ color: meta.textColor }}>
          {item.next_elapse ? `Следующий запуск: ${nextRun}` : 'Время следующего запуска неизвестно'}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.2 }}>
          {countdown
            ? `${countdown} · последний запуск: ${formatDateTime(item.last_trigger_at)}`
            : item.last_trigger_at
              ? `Последний запуск: ${formatDateTime(item.last_trigger_at)}`
              : 'Запусков ещё не было'}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', minWidth: { sm: 140 }, flexShrink: 0 }}>
        <Chip
          size="small"
          label={meta.label}
          sx={{ bgcolor: meta.ring, color: meta.textColor, fontWeight: 650 }}
        />
      </Box>
    </Box>
  );
};

export const UpdateScheduleAdminPage: FC = () => {
  const navigate = useNavigate();
  const { refresh_data: canRefreshData, manage_settings: canManageSettings } = useAdminCapabilities();
  const isAdmin = canRefreshData || canManageSettings;

  const [data, setData] = useState<UpdateScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      setData(await fetchUpdateSchedule());
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить расписание обновлений');
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const intervalId = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void load(true);
    }, 60_000);
    return () => window.clearInterval(intervalId);
  }, [load]);

  const counts = useMemo(() => {
    const result = { scheduled: 0, paused: 0, disabled: 0, notInstalled: 0, unknown: 0 };
    for (const item of data?.items ?? []) {
      if (item.state === 'scheduled') result.scheduled += 1;
      else if (item.state === 'paused') result.paused += 1;
      else if (item.state === 'disabled') result.disabled += 1;
      else if (item.state === 'not_installed') result.notInstalled += 1;
      else result.unknown += 1;
    }
    return result;
  }, [data]);

  if (!isAdmin) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: '#F4F7FD', p: 3 }}>
        <Paper variant="outlined" sx={{ width: '100%', maxWidth: 440, p: 4, borderRadius: 3, textAlign: 'center' }}>
          <Typography variant="h5" component="h1" fontWeight={700} color="#17345B">Доступ ограничен</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            Расписание обновлений доступно только администратору.
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
                Расписание обновлений
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
                Какие источники обновляются автоматически, по какому графику и когда следующий запуск.
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
                onClick={() => void load()}
                disabled={loading}
                sx={{ textTransform: 'none' }}
              >
                Обновить
              </Button>
            </Stack>
          </Stack>

          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 2 }}>
            <Chip size="small" label={`По расписанию: ${counts.scheduled}`} sx={{ bgcolor: '#EFFAF4', color: '#2E7D32', fontWeight: 650 }} />
            {counts.paused > 0 && (
              <Chip size="small" label={`Приостановлено: ${counts.paused}`} sx={{ bgcolor: '#FFF7E8', color: '#8A5200', fontWeight: 650 }} />
            )}
            {counts.disabled > 0 && (
              <Chip size="small" label={`Отключено: ${counts.disabled}`} sx={{ bgcolor: '#FFF1F0', color: '#B42318', fontWeight: 650 }} />
            )}
            {counts.notInstalled > 0 && (
              <Chip size="small" label={`Не установлено: ${counts.notInstalled}`} sx={{ bgcolor: '#FFF1F0', color: '#B42318', fontWeight: 650 }} />
            )}
            {counts.unknown > 0 && (
              <Chip size="small" label={`Неизвестно: ${counts.unknown}`} sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 650 }} />
            )}
            {data && (
              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center', ml: { sm: 'auto' } }}>
                Проверено: {formatDateTime(data.generated_at)}
              </Typography>
            )}
          </Stack>
        </Paper>

        {error && (
          <Alert
            severity="error"
            action={<Button color="inherit" size="small" onClick={() => void load()}>Повторить</Button>}
            sx={{ mb: 2, borderRadius: 2 }}
          >
            {error}
          </Alert>
        )}

        {data && !data.systemd_available && (
          <Alert severity="warning" sx={{ mb: 2, borderRadius: 2 }}>
            systemd недоступен, поэтому показано объявленное расписание из файлов проекта.
            Время следующего запуска можно увидеть только на сервере с systemd.
          </Alert>
        )}

        <Paper variant="outlined" sx={{ borderRadius: 3, borderColor: 'rgba(26,66,118,0.12)', overflow: 'hidden' }}>
          {loading && !data ? (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 7 }}>
              <CircularProgress size={30} />
            </Box>
          ) : data && data.items.length > 0 ? (
            <Box>
              {data.items.map((item) => (
                <ScheduleRow key={item.task_id} item={item} now={now} />
              ))}
            </Box>
          ) : (
            <Box sx={{ px: 2.5, py: 4 }}>
              <Typography variant="body2" color="text.secondary">
                Плановые обновления не найдены.
              </Typography>
            </Box>
          )}
        </Paper>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5, px: 0.5 }}>
          Пункты без таймера сюда не попадают — они запускаются только вручную.
        </Typography>
      </Container>
    </Box>
  );
};
