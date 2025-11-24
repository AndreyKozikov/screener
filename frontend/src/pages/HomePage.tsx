import React, { useState, useRef } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Tabs, Tab, Dialog, DialogTitle, DialogContent, DialogActions, Alert } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { FiltersPanel } from '../components/filters/FiltersPanel';
import { BondsTable } from '../components/bonds/BondsTable';
import { BondDetails } from '../components/bonds/BondDetails';
import { ZerocuponTable } from '../components/zerocupon/ZerocuponTable';
import { ForecastTable } from '../components/forecast/ForecastTable';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { refreshBondsData } from '../api/bonds';
import { useUiStore } from '../stores/uiStore';
import { useBondsStore } from '../stores/bondsStore';
import { getBondsDataForLLM, getZerocuponDataForLLM, getForecastDataForLLM } from '../utils/llmDataExport';
import { analyzeBondsWithLLM } from '../api/llm';
import type { BondsTableRef } from '../components/bonds/BondsTable';

/**
 * HomePage Component
 * 
 * Main page of the application displaying bonds screener
 */
export const HomePage: React.FC = () => {
  const triggerDataRefresh = useUiStore((state) => state.triggerDataRefresh);
  const setError = useBondsStore((state) => state.setError);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentTab, setCurrentTab] = useState(0);
  const bondsTableRef = useRef<BondsTableRef>(null);
  
  // LLM Analysis state
  const [isAnalysisParamsOpen, setIsAnalysisParamsOpen] = useState(false);
  const [isAnalysisResultOpen, setIsAnalysisResultOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [modelUsed, setModelUsed] = useState<string>('');
  const [isNoSelectionDialogOpen, setIsNoSelectionDialogOpen] = useState(false);

  const handleRefreshClick = async () => {
    if (isRefreshing) {
      return;
    }

    setIsRefreshing(true);
    setError(null);

    try {
      await refreshBondsData();
      triggerDataRefresh();
    } catch (error) {
      console.error('Failed to refresh bonds dataset', error);
      setError('Не удалось обновить данные облигаций. Попробуйте позже.');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleLLMAnalysisClick = () => {
    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }
      setIsAnalysisParamsOpen(true);
    } catch (error) {
      console.error('Error getting selected bonds:', error);
      setIsNoSelectionDialogOpen(true);
    }
  };

  const handleAnalysisParamsConfirm = async (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
  }) => {
    setIsAnalysisParamsOpen(false);
    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    // Open result dialog immediately to show loading state
    setIsAnalysisResultOpen(true);

    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }

      // Step 1: Load all data files FIRST (before sending to LLM)
      console.log('[LLM] Step 1: Loading data files...');
      const [bondsData, zerocuponData, forecastData] = await Promise.all([
        getBondsDataForLLM(Array.from(selectedBonds)),
        getZerocuponDataForLLM(params.zerocuponDateFrom, params.zerocuponDateTo),
        getForecastDataForLLM(params.forecastDate),
      ]);
      
      console.log('[LLM] Step 1 complete: All data files loaded');
      console.log(`[LLM] Bonds data size: ${bondsData.length} chars`);
      console.log(`[LLM] Zerocupon data size: ${zerocuponData.length} chars`);
      console.log(`[LLM] Forecast data size: ${forecastData.length} chars`);

      // Step 2: Send loaded data to LLM as files (data is already loaded, no reduction)
      // Note: This request has a 20-minute timeout to allow for complete LLM analysis
      console.log('[LLM] Step 2: Sending data to LLM as files...');
      console.log('[LLM] This may take several minutes. Please wait...');
      const response = await analyzeBondsWithLLM(
        bondsData,
        zerocuponData,
        forecastData,
        'gpt-5-mini' // Using GPT-5-mini model
      );

      setAnalysisResult(response.analysis);
      setModelUsed(response.model_used);
      setIsAnalysisResultOpen(true);
    } catch (error) {
      console.error('Error during LLM analysis:', error);
      setAnalysisError(
        error instanceof Error ? error.message : 'Не удалось выполнить анализ'
      );
      setIsAnalysisResultOpen(true);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* App Bar */}
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexGrow: 1 }}>
              <AccountBalanceIcon />
              <Box>
                <Typography variant="h6" component="h1" fontWeight={700}>
                  Скринер облигаций
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.8 }}>
                  Московская биржа
                </Typography>
              </Box>
            </Box>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleRefreshClick}
              startIcon={
                isRefreshing ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon />
              }
              disabled={isRefreshing}
              sx={{ mr: 1 }}
            >
              Обновить данные
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleLLMAnalysisClick}
              startIcon={<PsychologyIcon />}
            >
              Отправить на анализ LLM
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ flexGrow: 1, bgcolor: 'background.default', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
        <Container maxWidth={false} sx={{ px: 2, py: 2, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          {/* Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
            <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
              <Tab label="Скринер облигаций" />
              <Tab label="Кривая бескупонной доходности" />
              <Tab label="Среднесрочный прогноз Банка России" />
            </Tabs>
          </Box>

          {/* Tab Content */}
          {currentTab === 0 && (
            <Box sx={{ flexGrow: 1, display: 'flex', gap: 2, minHeight: 0 }}>
              {/* Left Side - Filters Panel */}
              <Box sx={{ width: { xs: '100%', md: '250px', lg: '200px', xl: '180px' }, flexShrink: 0 }}>
                <FiltersPanel />
              </Box>

              {/* Right Side - Table */}
              <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                <ErrorBoundary>
                  <BondsTable ref={bondsTableRef} />
                </ErrorBoundary>
              </Box>
            </Box>
          )}

          {currentTab === 1 && (
            <Box sx={{ flexGrow: 1, minHeight: 0 }}>
              <ZerocuponTable />
            </Box>
          )}

          {currentTab === 2 && (
            <Box sx={{ flexGrow: 1, minHeight: 0 }}>
              <ForecastTable />
            </Box>
          )}
        </Container>
      </Box>

      {/* Bond Details Drawer */}
      <BondDetails />

      {/* LLM Analysis Dialogs */}
      <AnalysisParamsDialog
        open={isAnalysisParamsOpen}
        onClose={() => setIsAnalysisParamsOpen(false)}
        onConfirm={handleAnalysisParamsConfirm}
      />
      <AnalysisResultDialog
        open={isAnalysisResultOpen}
        onClose={() => setIsAnalysisResultOpen(false)}
        analysis={analysisResult}
        isLoading={isAnalyzing}
        error={analysisError}
        modelUsed={modelUsed}
      />

      {/* No Selection Warning Dialog */}
      <Dialog
        open={isNoSelectionDialogOpen}
        onClose={() => setIsNoSelectionDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Не выбраны облигации</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            Для отправки на анализ LLM необходимо выбрать хотя бы одну облигацию в таблице.
            Пожалуйста, выберите одну или несколько облигаций и попробуйте снова.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsNoSelectionDialogOpen(false)} variant="contained" autoFocus>
            Понятно
          </Button>
        </DialogActions>
      </Dialog>

      {/* Footer */}
      <Box
        component="footer"
        sx={{
          py: 2,
          px: 2,
          mt: 'auto',
          bgcolor: 'background.paper',
          borderTop: 1,
          borderColor: 'divider',
        }}
      >
        <Container maxWidth="xl">
          <Typography variant="body2" color="text.secondary" align="center">
            © 2024 Bonds Screener. Данные предоставлены Московской биржей.
          </Typography>
        </Container>
      </Box>
    </Box>
  );
};

export default HomePage;
