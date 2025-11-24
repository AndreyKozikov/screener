import React, { useMemo, useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import type { BondListItem } from '../../types/bond';
import { formatNumber } from '../../utils/formatters';

interface ComparisonAnalysisDialogProps {
  open: boolean;
  onClose: () => void;
  bonds: BondListItem[];
}

interface ComparisonRow {
  name: string;
  ticker: string;
  maturity: string;
  price: string;
  ytm: string;
  coupon: string;
  duration: string;
  priceChange: string;
}

export const ComparisonAnalysisDialog: React.FC<ComparisonAnalysisDialogProps> = ({
  open,
  onClose,
  bonds,
}) => {
  // Calculate years until maturity
  const calculateYearsToMaturity = (matDate: string | null): number | null => {
    if (!matDate) return null;
    
    try {
      const today = new Date();
      const maturity = new Date(matDate);
      if (isNaN(maturity.getTime())) return null;
      
      const diffTime = maturity.getTime() - today.getTime();
      const diffYears = diffTime / (1000 * 60 * 60 * 24 * 365);
      
      return diffYears;
    } catch {
      return null;
    }
  };

  // Format maturity date as "ГГГГ (Yг)"
  const formatMaturity = (matDate: string | null): string => {
    if (!matDate) return '—';
    
    try {
      const date = new Date(matDate);
      if (isNaN(date.getTime())) return '—';
      
      const year = date.getFullYear();
      const yearsToMaturity = calculateYearsToMaturity(matDate);
      
      if (yearsToMaturity === null) {
        return `${year}`;
      }
      
      // Round to 1 decimal place
      const roundedYears = Math.round(yearsToMaturity * 10) / 10;
      return `${year} (${roundedYears}г)`;
    } catch {
      return '—';
    }
  };

  // Calculate modified duration in years
  const calculateModifiedDuration = (bond: BondListItem): number | null => {
    if (bond.DURATIONWAPRICE === null || bond.DURATIONWAPRICE === undefined) {
      return null;
    }
    
    // Convert from days to years
    const durationYears = bond.DURATIONWAPRICE / 365;
    
    // Modified Duration = D / (1 + YTM/100)
    // If YTM is not available, use duration directly
    if (bond.YIELDATPREVWAPRICE === null || bond.YIELDATPREVWAPRICE === undefined) {
      return durationYears;
    }
    
    const ytmDecimal = bond.YIELDATPREVWAPRICE / 100;
    const modifiedDuration = durationYears / (1 + ytmDecimal);
    
    return modifiedDuration;
  };

  // Calculate price change for -1% rate change
  const calculatePriceChange = (bond: BondListItem): number | null => {
    const md = calculateModifiedDuration(bond);
    if (md === null) return null;
    
    // PriceChangePercent = MD * 1 (where 1 = 1% change)
    return md * 1;
  };

  // Format price change as "+X,XX%"
  const formatPriceChange = (value: number | null): string => {
    if (value === null || value === undefined || isNaN(value)) return '—';
    
    const rounded = Math.round(value * 100) / 100;
    const sign = rounded >= 0 ? '+' : '';
    return `${sign}${rounded.toFixed(2)}%`;
  };

  // Prepare comparison data - calculate directly when dialog is open
  // Component is remounted with new key each time, so we can calculate directly
  let comparisonData: ComparisonRow[] = [];
  
  if (open && bonds.length > 0) {
    comparisonData = bonds.map((bond) => {
      const price = bond.PREVPRICE !== null && bond.PREVPRICE !== undefined
        ? formatNumber(bond.PREVPRICE, 2)
        : '—';
      
      const ytm = bond.YIELDATPREVWAPRICE !== null && bond.YIELDATPREVWAPRICE !== undefined
        ? formatNumber(bond.YIELDATPREVWAPRICE, 2)
        : '—';
      
      const coupon = bond.COUPONPERCENT !== null && bond.COUPONPERCENT !== undefined
        ? formatNumber(bond.COUPONPERCENT, 2)
        : '—';
      
      const duration = calculateModifiedDuration(bond);
      const durationStr = duration !== null
        ? formatNumber(duration, 2)
        : '—';
      
      const priceChange = formatPriceChange(calculatePriceChange(bond));
      
      return {
        name: bond.SHORTNAME || '—',
        ticker: bond.SECID || '—',
        maturity: formatMaturity(bond.MATDATE),
        price,
        ytm,
        coupon,
        duration: durationStr,
        priceChange,
      };
    });
  }

  // Generate markdown table
  const generateMarkdown = (): string => {
    const headers = [
      'Название',
      'Тикер',
      'Погашение',
      'Цена (%)',
      'YTM (%)',
      'Купон (%)',
      'Дюрация (MD)',
      'Рост цены при −1% ставки',
    ];
    
    // Calculate column widths for alignment
    const colWidths = headers.map((header, colIndex) => {
      let maxWidth = header.length;
      comparisonData.forEach((row) => {
        const values = [
          row.name,
          row.ticker,
          row.maturity,
          row.price,
          row.ytm,
          row.coupon,
          row.duration,
          row.priceChange,
        ];
        const cellValue = values[colIndex] || '';
        if (cellValue.length > maxWidth) {
          maxWidth = cellValue.length;
        }
      });
      return Math.max(maxWidth, 3); // Minimum width of 3 for separator
    });
    
    // Create header row
    const headerRow = '| ' + headers
      .map((header, i) => header.padEnd(colWidths[i]))
      .join(' | ') + ' |';
    
    // Create separator row
    const separatorRow = '| ' + colWidths.map((width) => '-'.repeat(width)).join(' | ') + ' |';
    
    // Create data rows
    const dataRows = comparisonData.map((row) => {
      const values = [
        row.name,
        row.ticker,
        row.maturity,
        row.price,
        row.ytm,
        row.coupon,
        row.duration,
        row.priceChange,
      ];
      return '| ' + values
        .map((value, i) => (value || '—').padEnd(colWidths[i]))
        .join(' | ') + ' |';
    });
    
    return [headerRow, separatorRow, ...dataRows].join('\n');
  };

  // Handle download markdown
  const handleDownloadMarkdown = () => {
    const markdown = generateMarkdown();
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `comparison_analysis_${new Date().toISOString().split('T')[0]}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      TransitionProps={{
        unmountOnExit: true,
      }}
      PaperProps={{
        sx: { height: '90vh' },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Сравнительный анализ</Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <TableContainer component={Paper} sx={{ maxHeight: 'calc(90vh - 200px)' }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Название</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Тикер</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Погашение</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Цена (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>YTM (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Купон (%)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Дюрация (MD)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Рост цены при −1% ставки</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {comparisonData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                      Нет данных для отображения
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                comparisonData.map((row, index) => (
                  <TableRow key={index} hover>
                    <TableCell align="left">{row.name}</TableCell>
                    <TableCell align="center">{row.ticker}</TableCell>
                    <TableCell align="center">{row.maturity}</TableCell>
                    <TableCell align="center">{row.price}</TableCell>
                    <TableCell align="center">{row.ytm}</TableCell>
                    <TableCell align="center">{row.coupon}</TableCell>
                    <TableCell align="center">{row.duration}</TableCell>
                    <TableCell align="center">{row.priceChange}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        {comparisonData.length > 0 && (
          <Button startIcon={<DownloadIcon />} onClick={handleDownloadMarkdown}>
            Сохранить в Markdown
          </Button>
        )}
        <Button onClick={onClose} variant="contained">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};

