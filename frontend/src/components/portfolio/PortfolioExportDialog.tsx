import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  FormLabel,
  Typography,
  Box,
} from '@mui/material';
import type { PortfolioExportFormat } from '../../utils/portfolioExport';

interface PortfolioExportDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (format: PortfolioExportFormat) => void;
  bondCount: number;
}

/**
 * Dialog for selecting portfolio export format
 */
export const PortfolioExportDialog: React.FC<PortfolioExportDialogProps> = ({
  open,
  onClose,
  onConfirm,
  bondCount,
}) => {
  const [selectedFormat, setSelectedFormat] = useState<PortfolioExportFormat>('secid-only');

  const handleConfirm = () => {
    onConfirm(selectedFormat);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Сохранить портфель</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            В портфеле {bondCount} {bondCount === 1 ? 'облигация' : bondCount < 5 ? 'облигации' : 'облигаций'}
          </Typography>
        </Box>
        <FormControl component="fieldset" fullWidth>
          <FormLabel component="legend">Выберите формат сохранения:</FormLabel>
          <RadioGroup
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value as PortfolioExportFormat)}
            sx={{ mt: 1 }}
          >
            <FormControlLabel
              value="secid-only"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight={500}>
                    Только SECID облигаций
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Сохраняет только идентификаторы облигаций. Файл небольшого размера. 
                    При загрузке портфеля данные облигаций всегда загружаются из базы данных.
                  </Typography>
                </Box>
              }
            />
            <FormControlLabel
              value="full"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight={500}>
                    Полные данные облигаций
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Сохраняет все параметры облигаций, включая данные о ценных бумагах, 
                    рыночные данные, историю доходности и купоны. Файл большего размера. 
                    При загрузке портфеля из файла извлекаются только SECID, 
                    и данные облигаций загружаются из базы данных (актуальные данные).
                  </Typography>
                </Box>
              }
            />
          </RadioGroup>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button onClick={handleConfirm} variant="contained" autoFocus>
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
};
