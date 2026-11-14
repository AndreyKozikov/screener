import { useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Container, Link, Paper, TextField, Typography } from '@mui/material';
import { apiClient } from '../api/client';
import { saveAuthSession } from '../utils/auth';
import { resolveSiteNavigationTarget, writeSavedHomePageView } from '../utils/siteNavigation';

type AuthResult = {
  access_token: string;
  user: {
    id: string;
    email: string;
    capabilities?: { refresh_data: boolean; manage_settings: boolean };
  };
};

export function AuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const redirectToPortfolio = (location.state as { from?: string } | null)?.from === 'portfolio';
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const { data } = await apiClient.post<AuthResult>(`/auth/${isRegister ? 'register' : 'login'}`, { email, password });
      saveAuthSession(data.access_token, data.user.email, data.user.capabilities);
      if (redirectToPortfolio) {
        writeSavedHomePageView(resolveSiteNavigationTarget('portfolio'));
      }
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить вход');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ py: { xs: 5, md: 10 } }}>
      <Paper elevation={2} sx={{ p: { xs: 3, sm: 5 }, borderRadius: 3 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>{isRegister ? 'Создать аккаунт' : 'Вход в аккаунт'}</Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>Аккаунт доступен с любого устройства после входа по email и паролю.</Typography>
        {redirectToPortfolio && <Alert severity="info" sx={{ mb: 2 }}>Раздел «Мой портфель» доступен только после входа в аккаунт.</Alert>}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box component="form" onSubmit={submit} sx={{ display: 'grid', gap: 2 }}>
          <TextField label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <TextField label="Пароль" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} value={password} onChange={(e) => setPassword(e.target.value)} required inputProps={{ minLength: 10, maxLength: 128 }} helperText="Минимум 10 символов" />
          <Button type="submit" variant="contained" size="large" disabled={busy}>{busy ? 'Подождите…' : isRegister ? 'Зарегистрироваться' : 'Войти'}</Button>
        </Box>
        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
          <Link component="button" type="button" onClick={() => { setIsRegister((value) => !value); setError(''); }}>
            {isRegister ? 'Уже есть аккаунт? Войти' : 'Создать аккаунт'}
          </Link>
          <Link component={RouterLink} to="/">На главную</Link>
        </Box>
      </Paper>
    </Container>
  );
}
