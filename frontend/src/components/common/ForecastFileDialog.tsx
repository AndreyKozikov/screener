import React, { useRef, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';

const ALLOWED_EXTENSION = '.md';
const ACCEPT = '.md';

interface ForecastFileDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (file: File) => void;
}

/**
 * Диалог выбора файла прогноза Банка России. Разрешён только формат .md.
 */
export const ForecastFileDialog: React.FC<ForecastFileDialogProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const name = file.name.toLowerCase();
    if (!name.endsWith(ALLOWED_EXTENSION)) {
      setError(`Допустим только формат ${ALLOWED_EXTENSION}`);
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleConfirm = () => {
    if (selectedFile) {
      onConfirm(selectedFile);
      setSelectedFile(null);
      setError(null);
      if (inputRef.current) {
        inputRef.current.value = '';
      }
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setError(null);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="forecast-file-dialog-title"
      PaperProps={{
        sx: {
          borderRadius: '20px',
          border: '1px solid #E2E8F0',
        },
      }}
    >
      <DialogTitle id="forecast-file-dialog-title">
        Выберите файл с прогнозом
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Допустим только формат Markdown ({ALLOWED_EXTENSION}). Файл будет сохранён на сервере в разделе «Среднесрочный прогноз Банка России».
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            onChange={handleFileChange}
            style={{ display: 'none' }}
            id="forecast-file-input"
          />
          <label htmlFor="forecast-file-input">
            <Button
              variant="outlined"
              component="span"
              startIcon={<UploadFileIcon />}
              disabled={!open}
            >
              Выбрать файл
            </Button>
          </label>
          {selectedFile && (
            <Typography variant="body2" color="text.secondary">
              {selectedFile.name}
            </Typography>
          )}
        </Box>
        {error && (
          <Typography variant="body2" color="error" sx={{ mt: 1 }}>
            {error}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Отмена</Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={!selectedFile}
        >
          Загрузить
        </Button>
      </DialogActions>
    </Dialog>
  );
};
