import React, { type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import AdminPanelSettingsOutlinedIcon from '@mui/icons-material/AdminPanelSettingsOutlined';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import SettingsSuggestOutlinedIcon from '@mui/icons-material/SettingsSuggestOutlined';
import SyncAltRoundedIcon from '@mui/icons-material/SyncAltRounded';
import { useAdminCapabilities } from '../contexts/adminCapabilitiesContext';
import { useUiStore } from '../stores/uiStore';

type AdminActionCardProps = {
  icon: ReactNode;
  title: string;
  description: string;
  actionLabel: string;
  accent: string;
  onClick: () => void;
};

const AdminActionCard: React.FC<AdminActionCardProps> = ({
  icon,
  title,
  description,
  actionLabel,
  accent,
  onClick,
}) => (
  <Paper
    component="section"
    variant="outlined"
    sx={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: 280,
      p: { xs: 2.5, md: 3 },
      borderRadius: 3,
      borderColor: 'rgba(26, 66, 118, 0.1)',
      bgcolor: 'rgba(255,255,255,0.94)',
      boxShadow: '0 12px 32px rgba(29, 61, 103, 0.06)',
    }}
  >
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 48,
        height: 48,
        mb: 2.5,
        borderRadius: 2.5,
        bgcolor: `${accent}14`,
        color: accent,
      }}
    >
      {icon}
    </Box>
    <Typography variant="h6" component="h2" fontWeight={700} color="#17345B">
      {title}
    </Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, lineHeight: 1.7, flex: 1 }}>
      {description}
    </Typography>
    <Button
      variant="outlined"
      endIcon={<ArrowForwardRoundedIcon />}
      onClick={onClick}
      sx={{ alignSelf: 'flex-start', mt: 2.5, borderRadius: 2, textTransform: 'none', fontWeight: 650 }}
    >
      {actionLabel}
    </Button>
  </Paper>
);

export const AdminPage: React.FC = () => {
  const navigate = useNavigate();
  const requestRefreshDialog = useUiStore((state) => state.requestRefreshDialog);
  const { refresh_data: canRefreshData, manage_settings: canManageSettings } = useAdminCapabilities();
  const isAdmin = canRefreshData || canManageSettings;

  if (!isAdmin) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: '#F4F7FD', p: 3 }}>
        <Paper variant="outlined" sx={{ width: '100%', maxWidth: 440, p: 4, borderRadius: 3, textAlign: 'center' }}>
          <AdminPanelSettingsOutlinedIcon sx={{ fontSize: 40, color: '#64748B', mb: 1 }} />
          <Typography variant="h5" component="h1" fontWeight={700} color="#17345B">
            Доступ ограничен
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            Админ-панель доступна только пользователям с правами администратора.
          </Typography>
          <Button variant="contained" onClick={() => navigate('/')} sx={{ textTransform: 'none' }}>
            На главную
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#F4F7FD', py: { xs: 2, md: 5 }, px: { xs: 1.5, md: 3 } }}>
      <Container maxWidth="lg" disableGutters>
        <Paper
          elevation={0}
          sx={{
            p: { xs: 2.5, md: 4 },
            borderRadius: 3,
            color: '#FFFFFF',
            background: 'linear-gradient(125deg, #123B70 0%, #1D5FA8 58%, #3D82C8 100%)',
            boxShadow: '0 18px 42px rgba(27, 76, 130, 0.2)',
          }}
        >
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between" gap={2}>
            <Box>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                <AdminPanelSettingsOutlinedIcon />
                <Chip
                  label="Администратор"
                  size="small"
                  sx={{ color: '#FFFFFF', bgcolor: 'rgba(255,255,255,0.16)', fontWeight: 600 }}
                />
              </Stack>
              <Typography variant="h4" component="h1" fontWeight={750} sx={{ fontSize: { xs: '1.7rem', md: '2.2rem' } }}>
                Админ-панель
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.75, color: 'rgba(255,255,255,0.82)' }}>
                Управление данными, публикациями и настройками BondsScreener.
              </Typography>
            </Box>
            <Button
              variant="outlined"
              startIcon={<HomeOutlinedIcon />}
              onClick={() => navigate('/')}
              sx={{
                flexShrink: 0,
                borderColor: 'rgba(255,255,255,0.45)',
                color: '#FFFFFF',
                borderRadius: 2,
                textTransform: 'none',
                '&:hover': { borderColor: '#FFFFFF', bgcolor: 'rgba(255,255,255,0.1)' },
              }}
            >
              На сайт
            </Button>
          </Stack>
        </Paper>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' }, gap: 2.5, mt: 3 }}>
          {canRefreshData && (
            <AdminActionCard
              icon={<SyncAltRoundedIcon />}
              title="Обновление данных"
              description="Запустите обновление облигаций, котировок, рейтингов и макроэкономических данных. Выберите нужные источники в общем окне обновления."
              actionLabel="Выбрать данные"
              accent="#1976D2"
              onClick={() => {
                requestRefreshDialog();
                navigate('/');
              }}
            />
          )}
          {canManageSettings && (
            <AdminActionCard
              icon={<ArticleOutlinedIcon />}
              title="Публикации блога"
              description="Создавайте статьи, редактируйте черновики, загружайте изображения и публикуйте материалы."
              actionLabel="Управлять статьями"
              accent="#8B5CF6"
              onClick={() => navigate('/blog-admin')}
            />
          )}
          {canManageSettings && (
            <AdminActionCard
              icon={<SettingsSuggestOutlinedIcon />}
              title="Настройки приложения"
              description="Настраивайте модели, провайдеров и параметры серверных сервисов."
              actionLabel="Открыть настройки"
              accent="#0F8B8D"
              onClick={() => navigate('/settings')}
            />
          )}
        </Box>

        <Alert severity="info" sx={{ mt: 3, borderRadius: 2 }}>
          Пункты панели отображаются только при наличии соответствующих прав администратора.
        </Alert>
      </Container>
    </Box>
  );
};

export default AdminPage;
