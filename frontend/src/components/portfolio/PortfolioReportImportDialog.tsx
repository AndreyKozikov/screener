import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { importPortfolioReport, type PortfolioReportImportResponse } from '../../api/portfolioReportImport';

interface PortfolioReportImportDialogProps {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

export const PortfolioReportImportDialog: React.FC<PortfolioReportImportDialogProps> = ({
  open,
  onClose,
  onImported,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [portfolioName, setPortfolioName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PortfolioReportImportResponse | null>(null);

  useEffect(() => {
    if (open) {
      setFile(null);
      setPortfolioName('');
      setError(null);
      setResult(null);
      setLoading(false);
    }
  }, [open]);

  const handleImport = async () => {
    if (!file || !portfolioName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const imported = await importPortfolioReport(file, portfolioName.trim());
      setResult(imported);
      onImported();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось импортировать отчёт.');
    } finally {
      setLoading(false);
    }
  };

  const period = result?.report_period_start && result.report_period_end
    ? `${result.report_period_start} — ${result.report_period_end}`
    : 'не определён';

  return (
    <Dialog open={open} onClose={loading ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Создать отдельный портфель из отчёта</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Отчёт будет сохранён как отдельный портфель и не изменит текущие облигации в таблице.
        </Typography>
        <TextField
          fullWidth
          required
          autoFocus
          label="Название портфеля"
          value={portfolioName}
          onChange={(event) => setPortfolioName(event.target.value)}
          inputProps={{ maxLength: 120 }}
          disabled={loading || Boolean(result)}
          sx={{ mb: 1.5 }}
        />
        <input
          ref={inputRef}
          type="file"
          accept=".html,.htm,text/html"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError(null);
            setResult(null);
            event.target.value = '';
          }}
          hidden
        />
        <Button
          fullWidth
          variant="outlined"
          startIcon={<UploadFileIcon />}
          onClick={() => inputRef.current?.click()}
          disabled={loading || Boolean(result)}
          sx={{ justifyContent: 'flex-start', mb: 1.5 }}
        >
          {file?.name ?? 'Выбрать HTML-отчёт'}
        </Button>
        {error && <Alert severity="error" sx={{ mb: 1.5 }}>{error}</Alert>}
        {result && (
          <Alert severity={result.parse_error_count ? 'warning' : 'success'}>
            <Typography variant="body2" fontWeight={600}>
              Портфель «{result.portfolio_name}» сохранён · период: {period}
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              Бумаг: {result.security_count}; сделок: {result.trade_count}; денежных операций: {result.cash_operation_count};
              выплат: {result.income_payment_count}; позиций: {result.position_count}; движений: {result.security_movement_count}.
            </Typography>
            {result.parse_error_count > 0 && (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Строк с ошибками распознавания: {result.parse_error_count}. Остальные данные сохранены.
              </Typography>
            )}
            {result.warnings.slice(0, 5).map((warning) => (
              <Typography key={warning} variant="body2" sx={{ mt: 0.5 }}>{warning}</Typography>
            ))}
          </Alert>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>{result ? 'Закрыть' : 'Отмена'}</Button>
        {!result && (
          <Button
            variant="contained"
            onClick={handleImport}
            disabled={loading || !file || !portfolioName.trim()}
            startIcon={loading ? <CircularProgress size={18} color="inherit" /> : undefined}
          >
            {loading ? 'Импортируем…' : 'Импортировать отдельно'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
