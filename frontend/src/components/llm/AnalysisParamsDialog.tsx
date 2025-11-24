import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { type Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import { fetchForecastDates } from '../../api/forecast';

dayjs.extend(customParseFormat);
dayjs.locale('ru');

interface AnalysisParamsDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
  }) => void;
}

export const AnalysisParamsDialog: React.FC<AnalysisParamsDialogProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  const [zerocuponDateFrom, setZerocuponDateFrom] = useState<Dayjs | null>(
    dayjs().subtract(1, 'year')
  );
  const [zerocuponDateTo, setZerocuponDateTo] = useState<Dayjs | null>(dayjs());
  const [forecastDate, setForecastDate] = useState<string>('');
  const [availableForecastDates, setAvailableForecastDates] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      const loadForecastDates = async () => {
        try {
          const dates = await fetchForecastDates();
          setAvailableForecastDates(dates);
          if (dates.length > 0 && !forecastDate) {
            setForecastDate(dates[0]);
          }
        } catch (err) {
          console.error('Error loading forecast dates:', err);
          setError('Не удалось загрузить список дат прогноза');
        }
      };
      void loadForecastDates();
    }
  }, [open, forecastDate]);

  const formatDateToString = (date: Dayjs | null): string | null => {
    if (!date) return null;
    return date.format('DD.MM.YYYY');
  };

  const handleConfirm = () => {
    const fromStr = formatDateToString(zerocuponDateFrom);
    const toStr = formatDateToString(zerocuponDateTo);

    if (!fromStr || !toStr) {
      setError('Необходимо указать период для кривой бескупонной доходности');
      return;
    }

    if (!forecastDate) {
      setError('Необходимо выбрать дату заседания для прогноза');
      return;
    }

    setError(null);
    onConfirm({
      zerocuponDateFrom: fromStr,
      zerocuponDateTo: toStr,
      forecastDate,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Параметры для анализа LLM</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 2 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <Typography variant="subtitle2" fontWeight={600}>
            Кривая бескупонной доходности
          </Typography>
          <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="ru">
            <DatePicker
              label="Дата от"
              value={zerocuponDateFrom}
              onChange={(newValue) => setZerocuponDateFrom(newValue)}
              format="DD.MM.YYYY"
              slotProps={{
                textField: {
                  fullWidth: true,
                  size: 'small',
                },
              }}
            />
            <DatePicker
              label="Дата до"
              value={zerocuponDateTo}
              onChange={(newValue) => setZerocuponDateTo(newValue)}
              format="DD.MM.YYYY"
              slotProps={{
                textField: {
                  fullWidth: true,
                  size: 'small',
                },
              }}
            />
          </LocalizationProvider>

          <Typography variant="subtitle2" fontWeight={600} sx={{ mt: 2 }}>
            Среднесрочный прогноз Банка России
          </Typography>
          <FormControl fullWidth size="small">
            <InputLabel>Дата заседания</InputLabel>
            <Select
              value={forecastDate}
              onChange={(e) => setForecastDate(e.target.value)}
              label="Дата заседания"
            >
              {availableForecastDates.map((date) => (
                <MenuItem key={date} value={date}>
                  {date}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button onClick={handleConfirm} variant="contained">
          Продолжить
        </Button>
      </DialogActions>
    </Dialog>
  );
};

