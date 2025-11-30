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
  FormControlLabel,
  Checkbox,
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
    includeZerocupon: boolean;
    includeForecast: boolean;
  }) => void;
}

/**
 * Calculate a date that is N working days ago (excluding weekends)
 * @param n Number of working days to go back
 * @returns Dayjs object representing the date N working days ago
 */
const getWorkingDaysAgo = (n: number): Dayjs => {
  let date = dayjs();
  let workingDaysCount = 0;
  
  while (workingDaysCount < n) {
    date = date.subtract(1, 'day');
    const dayOfWeek = date.day(); // 0 = Sunday, 6 = Saturday
    // Skip weekends (Saturday = 6, Sunday = 0)
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      workingDaysCount++;
    }
  }
  
  return date;
};

export const AnalysisParamsDialog: React.FC<AnalysisParamsDialogProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  // Default to 5 working days ago (excluding weekends)
  const [zerocuponDateFrom, setZerocuponDateFrom] = useState<Dayjs | null>(() => getWorkingDaysAgo(5));
  const [zerocuponDateTo, setZerocuponDateTo] = useState<Dayjs | null>(dayjs());
  const [forecastDate, setForecastDate] = useState<string>('');
  const [availableForecastDates, setAvailableForecastDates] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Checkboxes for data selection (default: both selected)
  const [includeZerocupon, setIncludeZerocupon] = useState<boolean>(true);
  const [includeForecast, setIncludeForecast] = useState<boolean>(true);

  useEffect(() => {
    if (open) {
      // Reset dates to default when dialog opens (5 working days ago)
      setZerocuponDateFrom(getWorkingDaysAgo(5));
      setZerocuponDateTo(dayjs());
      
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
    // Validate zerocupon dates only if zerocupon is included
    if (includeZerocupon) {
      const fromStr = formatDateToString(zerocuponDateFrom);
      const toStr = formatDateToString(zerocuponDateTo);

      if (!fromStr || !toStr) {
        setError('Необходимо указать период для кривой бескупонной доходности');
        return;
      }
    }

    // Validate forecast date only if forecast is included
    if (includeForecast) {
      if (!forecastDate) {
        setError('Необходимо выбрать дату заседания для прогноза');
        return;
      }
    }

    setError(null);
    const fromStr = formatDateToString(zerocuponDateFrom) || '';
    const toStr = formatDateToString(zerocuponDateTo) || '';
    
    onConfirm({
      zerocuponDateFrom: fromStr,
      zerocuponDateTo: toStr,
      forecastDate: forecastDate || '',
      includeZerocupon,
      includeForecast,
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
            Выбор данных для анализа
          </Typography>
          <FormControlLabel
            control={
              <Checkbox
                checked={includeZerocupon}
                onChange={(e) => setIncludeZerocupon(e.target.checked)}
              />
            }
            label="Включить кривую бескупонной доходности (КБД)"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={includeForecast}
                onChange={(e) => setIncludeForecast(e.target.checked)}
              />
            }
            label="Включить прогноз Банка России"
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 2 }}>
            Примечание: Данные по облигациям всегда отправляются для анализа
          </Typography>

          {includeZerocupon && (
            <>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mt: 2 }}>
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
            </>
          )}

          {includeForecast && (
            <>
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
            </>
          )}
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

