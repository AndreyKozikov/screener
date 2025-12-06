import React, { useRef, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { importPortfolioFromFile } from '../../utils/portfolioImport';

interface PortfolioImportDialogProps {
  open: boolean;
  onClose: () => void;
  onImport: (bonds: import('../../types/bond').BondListItem[]) => void;
}

/**
 * Dialog for importing portfolio from file
 */
export const PortfolioImportDialog: React.FC<PortfolioImportDialogProps> = ({
  open,
  onClose,
  onImport,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    bondsCount: number;
    errors: string[];
  } | null>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    // Check file extension
    if (!file.name.toLowerCase().endsWith('.json')) {
      setError('Файл должен иметь расширение .json');
      return;
    }

    setIsLoading(true);
    setError(null);
    setImportResult(null);

    try {
      const result = await importPortfolioFromFile(file);

      if (result.bonds.length === 0) {
        setError(
          'Не удалось загрузить данные облигаций. ' +
          'Убедитесь, что файл содержит корректные SECID облигаций, ' +
          'которые существуют в базе данных.'
        );
        setIsLoading(false);
        return;
      }

      setImportResult({
        bondsCount: result.bonds.length,
        errors: result.errors,
      });

      // Auto-import if successful
      if (result.bonds.length > 0) {
        onImport(result.bonds);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Не удалось загрузить портфель из файла'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setError(null);
    setImportResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Загрузить портфель из файла</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Выберите файл портфеля в формате JSON. Поддерживаются следующие форматы:
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 3 }}>
            <Typography component="li" variant="body2" color="text.secondary">
              Файл экспорта портфеля (только SECID)
            </Typography>
            <Typography component="li" variant="body2" color="text.secondary">
              Файл экспорта портфеля (полные данные)
            </Typography>
            <Typography component="li" variant="body2" color="text.secondary">
              Файл экспорта облигаций из скринера
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic' }}>
            Примечание: независимо от формата файла, из него извлекаются только SECID облигаций, 
            а актуальные данные облигаций загружаются из базы данных.
          </Typography>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <Button
            variant="outlined"
            startIcon={isLoading ? <CircularProgress size={20} /> : <UploadFileIcon />}
            onClick={handleSelectFile}
            disabled={isLoading}
            fullWidth
            sx={{ mt: 1 }}
          >
            {isLoading ? 'Загрузка...' : 'Выбрать файл'}
          </Button>

          {error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {error}
            </Alert>
          )}

          {importResult && (
            <Alert severity="success" sx={{ mt: 1 }}>
              <Typography variant="body2" fontWeight={500}>
                Портфель успешно загружен!
              </Typography>
              <Typography variant="body2">
                Загружено облигаций: {importResult.bondsCount}
              </Typography>
              {importResult.errors.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  {importResult.errors.map((err, index) => (
                    <Typography key={index} variant="body2" color="warning.main">
                      {err}
                    </Typography>
                  ))}
                </Box>
              )}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} variant="contained" autoFocus>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};
