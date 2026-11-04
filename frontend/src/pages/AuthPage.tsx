import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Container, Link, Paper, TextField, Typography } from '@mui/material';
import { apiClient } from '../api/client';

type AuthResult = { access_token: string; user: { id: string; email: string } };

export function AuthPage() {
  const navigate = useNavigate();
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
      localStorage.setItem('bonds-access-token', data.access_token);
      localStorage.setItem('bonds-user-email', data.user.email);
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
