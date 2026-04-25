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
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import CloseIcon from '@mui/icons-material/Close';
import { LoadingSpinner } from '../common/LoadingSpinner';
import type { BondPriceHistoryResponse } from '../../api/bonds';

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
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: '80vh',
          borderRadius: '12px',
        },
      }}
    >
      <DialogTitle sx={{ m: 0, p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
          История цены: {bondName} ({secid})
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
      <DialogContent dividers sx={{ p: 3, display: 'flex', flexDirection: 'column' }}>
        {loading && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <LoadingSpinner message="Загрузка истории цен..." />
          </Box>
        )}
        {error && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        )}
        {!loading && !error && data && (
          <Box sx={{ width: '100%', flex: 1, mt: 2 }}>
            {data.data.length === 0 ? (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Typography color="text.secondary">История торгов отсутствует для данной облигации.</Typography>
              </Box>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={data.data}
                  margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12, fill: '#666' }}
                    tickFormatter={(tick) => {
                      if (!tick) return '';
                      try {
                        return new Date(tick).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
                      } catch (e) {
                        return tick;
                      }
                    }}
                    axisLine={{ stroke: '#e0e0e0' }}
                    tickLine={false}
                    minTickGap={30}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: '#666' }}
                    axisLine={{ stroke: '#e0e0e0' }}
                    tickLine={false}
                    domain={['auto', 'auto']}
                    tickFormatter={(value) => (value != null ? `${value.toFixed(2)}%` : '')}
                    label={{ 
                        value: 'Цена (% от номинала)', 
                        angle: -90, 
                        position: 'insideLeft',
                        offset: 10,
                        style: { fontSize: 12, fill: '#666' }
                    }}
                  />
                  <Tooltip
                    contentStyle={{ 
                        borderRadius: '8px', 
                        border: 'none', 
                        boxShadow: '0 4px 12px rgba(0,0,0,0.1)' 
                    }}
                    labelFormatter={(label) => {
                      if (!label) return '';
                      try {
                        return new Date(label).toLocaleDateString('ru-RU', { 
                          day: 'numeric', 
                          month: 'long', 
                          year: 'numeric' 
                        });
                      } catch (e) {
                        return label;
                      }
                    }}
                    formatter={(value: number) => [value != null ? `${value.toFixed(2)}%` : '-', 'Цена']}
                  />
                  <Line
                    type="monotone"
                    dataKey="open"
                    name="Цена открытия"
                    stroke="#1976d2"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                    animationDuration={1000}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="outlined">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};
