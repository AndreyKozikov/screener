import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  CircularProgress,
  IconButton,
  Paper,
  Alert,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import ReactMarkdown from 'react-markdown';

interface AnalysisResultDialogProps {
  open: boolean;
  onClose: () => void;
  analysis: string | null;
  isLoading: boolean;
  error: string | null;
  modelUsed?: string;
}

export const AnalysisResultDialog: React.FC<AnalysisResultDialogProps> = ({
  open,
  onClose,
  analysis,
  isLoading,
  error,
  modelUsed,
}) => {
  const handleDownload = () => {
    if (!analysis) return;

    const blob = new Blob([analysis], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `bond_analysis_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose} // Prevent closing during loading
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Результат анализа LLM</Typography>
          {modelUsed && (
            <Typography variant="caption" color="text.secondary">
              Модель: {modelUsed}
            </Typography>
          )}
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {isLoading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', py: 8 }}>
            <CircularProgress size={60} />
            <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>
              Анализ выполняется...
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 500 }}>
              Это может занять несколько минут. Пожалуйста, не закрывайте это окно.
              <br />
              LLM обрабатывает большие объемы данных и выполняет детальный анализ.
            </Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!isLoading && !error && analysis && (
          <Paper
            sx={{
              p: 3,
              maxHeight: 'calc(90vh - 200px)',
              overflow: 'auto',
              bgcolor: 'background.default',
            }}
          >
            <ReactMarkdown
              components={{
                h1: ({ node, ...props }) => (
                  <Typography variant="h4" component="h1" gutterBottom {...props} />
                ),
                h2: ({ node, ...props }) => (
                  <Typography variant="h5" component="h2" gutterBottom {...props} />
                ),
                h3: ({ node, ...props }) => (
                  <Typography variant="h6" component="h3" gutterBottom {...props} />
                ),
                p: ({ node, ...props }) => (
                  <Typography variant="body1" paragraph {...props} />
                ),
                ul: ({ node, ...props }) => (
                  <Box component="ul" sx={{ pl: 3, mb: 2 }} {...props} />
                ),
                ol: ({ node, ...props }) => (
                  <Box component="ol" sx={{ pl: 3, mb: 2 }} {...props} />
                ),
                li: ({ node, ...props }) => (
                  <Typography component="li" variant="body1" {...props} />
                ),
                code: ({ node, ...props }) => (
                  <Box
                    component="code"
                    sx={{
                      bgcolor: 'action.hover',
                      px: 0.5,
                      borderRadius: 0.5,
                      fontFamily: 'monospace',
                    }}
                    {...props}
                  />
                ),
                pre: ({ node, ...props }) => (
                  <Box
                    component="pre"
                    sx={{
                      bgcolor: 'action.hover',
                      p: 2,
                      borderRadius: 1,
                      overflow: 'auto',
                      mb: 2,
                    }}
                    {...props}
                  />
                ),
              }}
            >
              {analysis}
            </ReactMarkdown>
          </Paper>
        )}

        {!isLoading && !error && !analysis && (
          <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
            Нет данных для отображения
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        {analysis && (
          <Button startIcon={<DownloadIcon />} onClick={handleDownload}>
            Сохранить в текстовом формате
          </Button>
        )}
        <Button onClick={onClose} variant="contained">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};

