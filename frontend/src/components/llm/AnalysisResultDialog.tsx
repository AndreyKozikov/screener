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
  Tabs,
  Tab,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface AnalysisResultDialogProps {
  open: boolean;
  onClose: () => void;
  analysis: string | null;
  stages?: {
    stage1_forecast: string | null;
    stage2_zerocupon: string | null;
    stage3_bonds: string | null;
  };
  isLoading: boolean;
  error: string | null;
  modelUsed?: string;
}

export const AnalysisResultDialog: React.FC<AnalysisResultDialogProps> = ({
  open,
  onClose,
  analysis,
  stages,
  isLoading,
  error,
  modelUsed,
}) => {
  const [currentTab, setCurrentTab] = useState(0);

  // Определяем доступные закладки (без этапа 3)
  const hasStages = stages && (stages.stage1_forecast || stages.stage2_zerocupon);
  const tabs = [
    { label: 'Итоговый отчет', value: 'final', content: analysis },
    ...(stages?.stage1_forecast ? [{ label: 'Результат анализа прогноза ЦБ', value: 'stage1', content: stages.stage1_forecast }] : []),
    ...(stages?.stage2_zerocupon ? [{ label: 'Результат анализа кривой бескупонной доходности', value: 'stage2', content: stages.stage2_zerocupon }] : []),
  ];

  const handleDownload = () => {
    if (!analysis && !hasStages) return;

    // Формируем markdown документ со всеми этапами
    const markdownParts: string[] = [];
    
    markdownParts.push('# Анализ облигаций\n');
    if (modelUsed) {
      markdownParts.push(`**Модель:** ${modelUsed}\n`);
    }
    markdownParts.push(`**Дата анализа:** ${new Date().toLocaleString('ru-RU')}\n\n`);
    markdownParts.push('---\n\n');

    // Результат анализа прогноза ЦБ
    if (stages?.stage1_forecast) {
      markdownParts.push('## Результат анализа прогноза ЦБ\n\n');
      markdownParts.push(stages.stage1_forecast);
      markdownParts.push('\n\n---\n\n');
    }

    // Результат анализа кривой бескупонной доходности
    if (stages?.stage2_zerocupon) {
      markdownParts.push('## Результат анализа кривой бескупонной доходности\n\n');
      markdownParts.push(stages.stage2_zerocupon);
      markdownParts.push('\n\n---\n\n');
    }

    // Этап 3 исключен из отображения, но оставляем в файле для полноты
    if (stages?.stage3_bonds) {
      markdownParts.push('## Нормализация данных по облигациям\n\n');
      markdownParts.push(stages.stage3_bonds);
      markdownParts.push('\n\n---\n\n');
    }

    // Итоговый отчет
    if (analysis) {
      markdownParts.push('## Итоговый аналитический отчет\n\n');
      markdownParts.push(analysis);
    }

    const markdownContent = markdownParts.join('');
    const blob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `bond_analysis_${new Date().toISOString().split('T')[0]}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
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

        {!isLoading && !error && (analysis || hasStages) && (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {tabs.length > 1 && (
              <Tabs
                value={currentTab}
                onChange={handleTabChange}
                variant="scrollable"
                scrollButtons="auto"
                sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
              >
                {tabs.map((tab, index) => (
                  <Tab key={tab.value} label={tab.label} value={index} />
                ))}
              </Tabs>
            )}
            <Paper
              sx={{
                p: 3,
                maxHeight: 'calc(90vh - 250px)',
                overflow: 'auto',
                bgcolor: 'background.default',
                flex: 1,
              }}
            >
              {tabs[currentTab]?.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
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
                    table: ({ node, ...props }) => (
                      <Box
                        sx={{
                          overflowX: 'auto',
                          mb: 3,
                          mt: 2,
                          width: '100%',
                          display: 'block',
                        }}
                      >
                        <Box
                          component="table"
                          sx={{
                            borderCollapse: 'collapse',
                            width: '100%',
                            minWidth: '100%',
                            display: 'table',
                            '& th, & td': {
                              border: '1px solid',
                              borderColor: 'divider',
                              padding: '10px 14px',
                              textAlign: 'left',
                              verticalAlign: 'top',
                            },
                            '& th': {
                              bgcolor: 'primary.main',
                              color: 'primary.contrastText',
                              fontWeight: 600,
                              fontSize: '0.875rem',
                              whiteSpace: 'nowrap',
                            },
                            '& td': {
                              fontSize: '0.875rem',
                            },
                            '& tr:nth-of-type(even)': {
                              bgcolor: 'action.hover',
                            },
                            '& tr:hover': {
                              bgcolor: 'action.selected',
                            },
                          }}
                          {...props}
                        />
                      </Box>
                    ),
                    thead: ({ node, ...props }) => (
                      <Box component="thead" {...props} />
                    ),
                    tbody: ({ node, ...props }) => (
                      <Box component="tbody" {...props} />
                    ),
                    tr: ({ node, ...props }) => (
                      <Box component="tr" {...props} />
                    ),
                    th: ({ node, ...props }) => (
                      <Box component="th" {...props} />
                    ),
                    td: ({ node, ...props }) => (
                      <Box component="td" {...props} />
                    ),
                  }}
                >
                  {tabs[currentTab].content || ''}
                </ReactMarkdown>
              ) : (
                <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
                  Нет данных для отображения
                </Typography>
              )}
            </Paper>
          </Box>
        )}

        {!isLoading && !error && !analysis && (
          <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
            Нет данных для отображения
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        {(analysis || hasStages) && (
          <Button startIcon={<DownloadIcon />} onClick={handleDownload}>
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

