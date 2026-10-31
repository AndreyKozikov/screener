import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
} from '@mui/material';
import Plot from 'react-plotly.js';
import CloseIcon from '@mui/icons-material/Close';
import { LoadingSpinner } from '../common/LoadingSpinner';
import type { BondPriceHistoryResponse } from '../../api/bonds';

const russianPlotlyLocales = {
  ru: {
    format: {
      months: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
      shortMonths: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
    },
  },
};

interface PriceHistoryDialogProps {
  open: boolean;
  onClose: () => void;
  secid: string;
  bondName: string;
  data: BondPriceHistoryResponse | null;
  loading: boolean;
  error: string | null;
}

export const PriceHistoryDialog: React.FC<PriceHistoryDialogProps> = ({
  open,
  onClose,
  secid,
  bondName,
  data,
  loading,
  error,
}) => {
  const points = data?.data ?? [];
  const sortedPoints = [...points].sort((a, b) => a.date.localeCompare(b.date));
  const hasValidPrices = sortedPoints.some((point) => point.open != null && Number.isFinite(point.open) && point.open > 0);
  const firstDate = sortedPoints[0]?.date.slice(0, 10);
  const lastDate = sortedPoints[sortedPoints.length - 1]?.date.slice(0, 10);
  const firstTimestamp = firstDate ? Date.parse(`${firstDate}T00:00:00Z`) : Number.NaN;
  const lastTimestamp = lastDate ? Date.parse(`${lastDate}T00:00:00Z`) : Number.NaN;
  const dateRangeDays = Number.isFinite(firstTimestamp) && Number.isFinite(lastTimestamp)
    ? Math.max(0, (lastTimestamp - firstTimestamp) / 86_400_000)
    : 0;
  const tickCount = dateRangeDays === 0 ? 1 : Math.min(8, Math.ceil(dateRangeDays / 90) + 1);
  const tickTimestamps = tickCount === 1
    ? [firstTimestamp]
    : Array.from({ length: tickCount }, (_, index) => firstTimestamp + ((lastTimestamp - firstTimestamp) * index) / (tickCount - 1));
  const dateTickLabels = tickTimestamps.map((timestamp) => new Date(timestamp).toLocaleDateString('ru-RU', {
    timeZone: 'UTC',
    ...(dateRangeDays > 120 ? { month: 'short', year: 'numeric' } : { day: '2-digit', month: 'short' }),
  }));
  const chartData = [{
    x: sortedPoints.map((point) => point.date),
    y: sortedPoints.map((point) => point.open != null && Number.isFinite(point.open) && point.open > 0 ? point.open : null),
    type: 'scatter' as const,
    mode: 'lines' as const,
    name: 'Цена открытия',
    line: { color: '#1677f2', width: 2.5 },
    hovertemplate: '%{x|%d.%m.%Y}<br>Цена: <b>%{y:.2f}%</b><extra></extra>',
  }];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: { xs: '88vh', md: '82vh' },
          minHeight: 420,
          borderRadius: '16px',
        },
      }}
    >
      <DialogTitle sx={{ m: 0, px: 2.5, py: 1.75, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e3ecf8' }}>
        <Typography component="div" sx={{ fontSize: '1rem', fontWeight: 600, color: '#16345e', textTransform: 'none', letterSpacing: 0 }}>
          История торгов: {bondName} ({secid})
        </Typography>
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{
            color: (theme) => theme.palette.grey[500],
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ p: { xs: 1.5, sm: 2 }, display: 'flex', flexDirection: 'column', minHeight: 0, bgcolor: '#fbfdff' }}>
        {loading && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <LoadingSpinner message="Загрузка истории торгов..." />
          </Box>
        )}
        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        )}
        {!loading && !error && data && (
          <Box sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {points.length === 0 || !hasValidPrices ? (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Typography color="text.secondary">
                  {points.length === 0
                    ? 'История торгов отсутствует для данной облигации.'
                    : 'Нет корректных значений цены для отображения.'}
                </Typography>
              </Box>
            ) : (
              <Box sx={{ width: '100%', flex: 1, minHeight: 320, border: '1px solid #e3ecf8', borderRadius: 2, bgcolor: '#fff', overflow: 'hidden' }}>
                <Plot
                  data={chartData}
                  layout={{
                    autosize: true,
                    separators: ', ',
                    font: { family: 'Source Sans 3 Variable, Source Sans 3, sans-serif', color: '#334a68' },
                    xaxis: {
                      type: 'date',
                      tickmode: 'array',
                      tickvals: tickTimestamps.map((timestamp) => new Date(timestamp).toISOString()),
                      ticktext: dateTickLabels,
                      tickangle: 0,
                      automargin: true,
                      showgrid: true,
                      gridcolor: '#e9f0fa',
                      zeroline: false,
                      ticks: 'outside',
                      tickfont: { size: 12, color: '#56708f' },
                    },
                    yaxis: {
                      title: { text: 'Цена, % от номинала', font: { size: 13, color: '#56708f' } },
                      tickformat: '.2f',
                      ticksuffix: '%',
                      autorange: true,
                      rangemode: 'normal',
                      automargin: true,
                      gridcolor: '#e9f0fa',
                      zeroline: false,
                      ticks: 'outside',
                      tickfont: { size: 12, color: '#56708f' },
                    },
                    showlegend: false,
                    hovermode: 'x unified',
                    hoverlabel: {
                      bgcolor: '#ffffff',
                      bordercolor: '#cbd9eb',
                      align: 'left',
                      namelength: -1,
                      font: { family: 'Source Sans 3 Variable, Source Sans 3, sans-serif', size: 11, color: '#334a68' },
                    },
                    margin: { l: 70, r: 12, t: 16, b: 38 },
                    plot_bgcolor: 'rgba(255,255,255,0)',
                    paper_bgcolor: 'rgba(255,255,255,0)',
                  }}
                  config={{ responsive: true, displayModeBar: 'hover', scrollZoom: false, displaylogo: false, locale: 'ru', locales: russianPlotlyLocales }}
                  style={{ width: '100%', height: '100%' }}
                />
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: '1px solid #e3ecf8' }}>
        <Button onClick={onClose} variant="outlined">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};



