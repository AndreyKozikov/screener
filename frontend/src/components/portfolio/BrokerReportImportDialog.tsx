import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import type { PortfolioBond } from '../../types/bond';
import { loadBrokerReportPositions } from '../../utils/portfolioImport';
import {
  importBrokerReport,
  type BrokerPortfolioImportMode,
  type BrokerPortfolioImportResponse,
} from '../../api/brokerPortfolio';

interface BrokerReportImportDialogProps {
  open: boolean;
  hasExistingPortfolio: boolean;
  onClose: () => void;
  onImport: (bonds: PortfolioBond[], mode: BrokerPortfolioImportMode) => void;
}

export const BrokerReportImportDialog: React.FC<BrokerReportImportDialogProps> = ({
  open,
  hasExistingPortfolio,
  onClose,
  onImport,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    bonds: PortfolioBond[];
    importedCount: number;
    warnings: string[];
  } | null>(null);

  useEffect(() => {
    if (open) {
      setFile(null);
      setError(null);
      setResult(null);
      setIsLoading(false);
    }
  }, [open]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
    setError(null);
    setResult(null);
    // Let the same file be selected again after a failed parse.
    event.target.value = '';
  };

  const handleParse = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const parsedReport: BrokerPortfolioImportResponse = await importBrokerReport(file);
      const loadedPositions = await loadBrokerReportPositions(parsedReport.positions);
      const warnings = [...parsedReport.warnings];
      if (loadedPositions.unmatchedIsins.length > 0) {
        const unmatched = loadedPositions.unmatchedIsins;
        warnings.push(
          `В данных скринера не найдены ISIN: ${unmatched.slice(0, 10).join(', ')}` +
          (unmatched.length > 10 ? ` и ещё ${unmatched.length - 10}` : ''),
        );
      }

      setResult({
        bonds: loadedPositions.bonds,
        importedCount: parsedReport.imported_count,
        warnings,
      });
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : 'Не удалось разобрать отчёт брокера.');
    } finally {
      setIsLoading(false);
    }
  };

  const applyImport = (mode: BrokerPortfolioImportMode) => {
    if (!result) return;
    onImport(result.bonds, mode);
    onClose();
  };

  return (
    <Dialog open={open} onClose={isLoading ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Импорт портфеля из отчёта брокера</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Будут загружены остатки из колонки «Конец периода»: ISIN, количество и рыночная стоимость без НКД.
            Средняя цена рассчитывается как стоимость ÷ количество ÷ номинал × 100.
          </Typography>

          <input
            ref={fileInputRef}
            type="file"
            accept=".html,.htm,text/html"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
          >
            {file ? file.name : 'Выбрать HTML-отчёт'}
          </Button>
          {file && !result && (
            <Button
              variant="contained"
              onClick={handleParse}
              disabled={isLoading}
              startIcon={isLoading ? <CircularProgress size={18} color="inherit" /> : undefined}
            >
              {isLoading ? 'Разбираем отчёт…' : 'Прочитать отчёт'}
            </Button>
          )}

          {error && <Alert severity="error">{error}</Alert>}
          {result && (
            <Alert severity={result.warnings.length || !result.bonds.length ? 'warning' : 'success'}>
              <Typography variant="body2" fontWeight={600}>
                В отчёте найдено позиций: {result.importedCount}; загружено из скринера: {result.bonds.length}
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Средняя цена отражает оценку на конец периода из отчёта, а не историю сделок.
              </Typography>
              {result.warnings.map((warning, index) => (
                <Typography key={`${index}-${warning}`} variant="body2" sx={{ mt: 0.5 }}>
                  {warning}
                </Typography>
              ))}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>Отмена</Button>
        {result && hasExistingPortfolio && (
          <>
            <Button onClick={() => applyImport('merge')} variant="outlined" disabled={!result.bonds.length}>
              Сложить с портфелем
            </Button>
            <Button onClick={() => applyImport('replace')} variant="contained" color="warning" disabled={!result.bonds.length}>
              Загрузить заново
            </Button>
          </>
        )}
        {result && !hasExistingPortfolio && (
          <Button onClick={() => applyImport('replace')} variant="contained" disabled={!result.bonds.length}>
            Загрузить портфель
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
