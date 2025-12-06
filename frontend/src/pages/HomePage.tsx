import React, { useState, useRef } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Tabs, Tab, Dialog, DialogTitle, DialogContent, DialogActions, Alert } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import { SearchFilter } from '../components/filters/SearchFilter';
import { FiltersModal } from '../components/filters/FiltersModal';
import { BondsTable } from '../components/bonds/BondsTable';
import { BondDetails } from '../components/bonds/BondDetails';
import { ZerocuponTable } from '../components/zerocupon/ZerocuponTable';
import { ForecastTable } from '../components/forecast/ForecastTable';
import { PortfolioTable } from '../components/portfolio/PortfolioTable';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { refreshBondsData, refreshCouponsData } from '../api/bonds';
import { refreshZerocuponData } from '../api/zerocupon';
import { refreshRatingsData } from '../api/rating';
import { refreshEmitentsData } from '../api/emitent';
import { useUiStore } from '../stores/uiStore';
import { useBondsStore } from '../stores/bondsStore';
import { getBondsDataForLLM, getZerocuponDataForLLM, getForecastDataForLLM } from '../utils/llmDataExport';
import { analyzeBondsWithLLM } from '../api/llm';
import { analyzeBondsWithQwen } from '../api/qwen';
import { analyzeBondsWithGrok } from '../api/grok';
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
  const [isRefreshingRatings, setIsRefreshingRatings] = useState(false);
  const [isRefreshingEmitents, setIsRefreshingEmitents] = useState(false);
  const [isRefreshingCoupons, setIsRefreshingCoupons] = useState(false);
  const [currentTab, setCurrentTab] = useState(0);
  const bondsTableRef = useRef<BondsTableRef>(null);
  
  // LLM Analysis state
  const [isAnalysisParamsOpen, setIsAnalysisParamsOpen] = useState(false);
  const [isAnalysisResultOpen, setIsAnalysisResultOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisStages, setAnalysisStages] = useState<{
    stage1_forecast: string | null;
    stage2_zerocupon: string | null;
    stage3_bonds: string | null;
  }>({
    stage1_forecast: null,
    stage2_zerocupon: null,
    stage3_bonds: null,
  });
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [modelUsed, setModelUsed] = useState<string>('');
  const [isNoSelectionDialogOpen, setIsNoSelectionDialogOpen] = useState(false);
  
  // Qwen Analysis state
  const [isQwenParamsOpen, setIsQwenParamsOpen] = useState(false);
  const [isQwenAnalyzing, setIsQwenAnalyzing] = useState(false);
  
  // Grok Analysis state
  const [isGrokParamsOpen, setIsGrokParamsOpen] = useState(false);
  const [isGrokAnalyzing, setIsGrokAnalyzing] = useState(false);
  const [isFiltersModalOpen, setIsFiltersModalOpen] = useState(false);

  const handleRefreshRatingsClick = async () => {
    if (isRefreshingRatings) {
      return;
    }

    setIsRefreshingRatings(true);
    setError(null);

    try {
      // Refresh ratings data - backend handles all processing
      await refreshRatingsData();
    } catch (error) {
      console.error('Failed to refresh ratings', error);
      setError('Не удалось обновить рейтинги. Попробуйте позже.');
    } finally {
      setIsRefreshingRatings(false);
    }
  };

  const handleRefreshEmitentsClick = async () => {
    if (isRefreshingEmitents) {
      return;
    }

    setIsRefreshingEmitents(true);
    setError(null);

    try {
      // Refresh emitents data - backend handles all processing
      await refreshEmitentsData();
    } catch (error) {
      console.error('Failed to refresh emitents', error);
      setError('Не удалось обновить данные эмитентов. Попробуйте позже.');
    } finally {
      setIsRefreshingEmitents(false);
    }
  };

  const handleRefreshCouponsClick = async () => {
    if (isRefreshingCoupons) {
      return;
    }

    setIsRefreshingCoupons(true);
    setError(null);

    try {
      // Refresh coupons data - backend handles all processing
      await refreshCouponsData();
    } catch (error) {
      console.error('Failed to refresh coupons', error);
      setError('Не удалось обновить данные купонов. Попробуйте позже.');
    } finally {
      setIsRefreshingCoupons(false);
    }
  };

  const handleRefreshClick = async () => {
    if (isRefreshing) {
      return;
    }

    setIsRefreshing(true);
    setError(null);

    try {
      // Refresh bonds data
      await refreshBondsData();
      
      // Refresh zero-coupon yield curve data
      try {
        await refreshZerocuponData();
      } catch (zerocuponError) {
        console.error('Failed to refresh zerocupon data', zerocuponError);
        // Don't fail the whole refresh if zerocupon update fails
      }
      
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

  const handleQwenAnalysisClick = () => {
    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }
      setIsQwenParamsOpen(true);
    } catch (error) {
      console.error('Error getting selected bonds:', error);
      setIsNoSelectionDialogOpen(true);
    }
  };

  const handleGrokAnalysisClick = () => {
    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }
      setIsGrokParamsOpen(true);
    } catch (error) {
      console.error('Error getting selected bonds:', error);
      setIsNoSelectionDialogOpen(true);
    }
  };

  const handleQwenAnalysisParamsConfirm = async (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
    includeZerocupon: boolean;
    includeForecast: boolean;
  }) => {
    setIsQwenParamsOpen(false);
    setIsQwenAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisStages({
      stage1_forecast: null,
      stage2_zerocupon: null,
      stage3_bonds: null,
    });
    // Open result dialog immediately to show loading state
    setIsAnalysisResultOpen(true);

    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }

      // Step 1: Load data files conditionally based on checkboxes
      console.log('[QWEN] Step 1: Loading data files...');
      const bondsData = await getBondsDataForLLM(Array.from(selectedBonds));
      
      let zerocuponData = '';
      let forecastData = '';
      
      if (params.includeZerocupon) {
        zerocuponData = await getZerocuponDataForLLM(params.zerocuponDateFrom, params.zerocuponDateTo);
      }
      if (params.includeForecast) {
        forecastData = await getForecastDataForLLM(params.forecastDate);
      }
      
      console.log('[QWEN] Step 1 complete: Data files loaded');
      console.log(`[QWEN] Bonds data size: ${bondsData.length} chars`);
      if (params.includeZerocupon) {
        console.log(`[QWEN] Zerocupon data size: ${zerocuponData.length} chars`);
      }
      if (params.includeForecast) {
        console.log(`[QWEN] Forecast data size: ${forecastData.length} chars`);
      }

      // Step 2: Send loaded data to Qwen (data is already loaded, no reduction)
      // Note: This request has a 20-minute timeout to allow for complete Qwen analysis
      console.log('[QWEN] Step 2: Sending data to Qwen 3 via OpenRouter as files...');
      console.log('[QWEN] This may take several minutes. Please wait...');
      const response = await analyzeBondsWithQwen(
        bondsData,
        zerocuponData,
        forecastData,
        'qwen/qwen3-235b-a22b:free',
        params.includeZerocupon,
        params.includeForecast
      );

      setAnalysisResult(response.analysis);
      setAnalysisStages({
        stage1_forecast: response.stage1_forecast || null,
        stage2_zerocupon: response.stage2_zerocupon || null,
        stage3_bonds: response.stage3_bonds || null,
      });
      setModelUsed(response.model_used);
      setIsAnalysisResultOpen(true);
    } catch (error) {
      console.error('Error during Qwen analysis:', error);
      setAnalysisError(
        error instanceof Error ? error.message : 'Не удалось выполнить анализ Qwen 3'
      );
      setIsAnalysisResultOpen(true);
    } finally {
      setIsQwenAnalyzing(false);
    }
  };

  const handleGrokAnalysisParamsConfirm = async (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
    includeZerocupon: boolean;
    includeForecast: boolean;
  }) => {
    setIsGrokParamsOpen(false);
    setIsGrokAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisStages({
      stage1_forecast: null,
      stage2_zerocupon: null,
      stage3_bonds: null,
    });
    // Open result dialog immediately to show loading state
    setIsAnalysisResultOpen(true);

    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }

      // Step 1: Load data files conditionally based on checkboxes
      console.log('[GROK] Step 1: Loading data files...');
      const bondsData = await getBondsDataForLLM(Array.from(selectedBonds));
      
      let zerocuponData = '';
      let forecastData = '';
      
      if (params.includeZerocupon) {
        zerocuponData = await getZerocuponDataForLLM(params.zerocuponDateFrom, params.zerocuponDateTo);
      }
      if (params.includeForecast) {
        forecastData = await getForecastDataForLLM(params.forecastDate);
      }
      
      console.log('[GROK] Step 1 complete: Data files loaded');
      console.log(`[GROK] Bonds data size: ${bondsData.length} chars`);
      if (params.includeZerocupon) {
        console.log(`[GROK] Zerocupon data size: ${zerocuponData.length} chars`);
      }
      if (params.includeForecast) {
        console.log(`[GROK] Forecast data size: ${forecastData.length} chars`);
      }

      // Step 2: Send loaded data to Grok (data is already loaded, no reduction)
      // Note: This request has a 20-minute timeout to allow for complete Grok analysis
      console.log('[GROK] Step 2: Sending data to Grok 4.1 Fast via OpenRouter as files...');
      console.log('[GROK] This may take several minutes. Please wait...');
      const response = await analyzeBondsWithGrok(
        bondsData,
        zerocuponData,
        forecastData,
        'x-ai/grok-4.1-fast:free',
        params.includeZerocupon,
        params.includeForecast
      );

      setAnalysisResult(response.analysis);
      setAnalysisStages({
        stage1_forecast: response.stage1_forecast || null,
        stage2_zerocupon: response.stage2_zerocupon || null,
        stage3_bonds: response.stage3_bonds || null,
      });
      setModelUsed(response.model_used);
      setIsAnalysisResultOpen(true);
    } catch (error) {
      console.error('Error during Grok analysis:', error);
      setAnalysisError(
        error instanceof Error ? error.message : 'Не удалось выполнить анализ Grok 4.1 Fast'
      );
      setIsAnalysisResultOpen(true);
    } finally {
      setIsGrokAnalyzing(false);
    }
  };

  const handleAnalysisParamsConfirm = async (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
    includeZerocupon: boolean;
    includeForecast: boolean;
  }) => {
    setIsAnalysisParamsOpen(false);
    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisStages({
      stage1_forecast: null,
      stage2_zerocupon: null,
      stage3_bonds: null,
    });
    // Open result dialog immediately to show loading state
    setIsAnalysisResultOpen(true);

    try {
      // Get selected bonds
      const selectedBonds = bondsTableRef.current?.getSelectedBonds();
      if (!selectedBonds || selectedBonds.size === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }

      // Step 1: Load data files conditionally based on checkboxes
      console.log('[LLM] Step 1: Loading data files...');
      const bondsData = await getBondsDataForLLM(Array.from(selectedBonds));
      
      let zerocuponData = '';
      let forecastData = '';
      
      if (params.includeZerocupon) {
        zerocuponData = await getZerocuponDataForLLM(params.zerocuponDateFrom, params.zerocuponDateTo);
      }
      if (params.includeForecast) {
        forecastData = await getForecastDataForLLM(params.forecastDate);
      }
      
      console.log('[LLM] Step 1 complete: Data files loaded');
      console.log(`[LLM] Bonds data size: ${bondsData.length} chars`);
      if (params.includeZerocupon) {
        console.log(`[LLM] Zerocupon data size: ${zerocuponData.length} chars`);
      }
      if (params.includeForecast) {
        console.log(`[LLM] Forecast data size: ${forecastData.length} chars`);
      }

      // Step 2: Send loaded data to LLM as files (data is already loaded, no reduction)
      // Note: This request has a 20-minute timeout to allow for complete LLM analysis
      console.log('[LLM] Step 2: Sending data to LLM as files...');
      console.log('[LLM] This may take several minutes. Please wait...');
      const response = await analyzeBondsWithLLM(
        bondsData,
        zerocuponData,
        forecastData,
        'gpt-5.1', // Using GPT-5.1 model
        params.includeZerocupon,
        params.includeForecast
      );

      setAnalysisResult(response.analysis);
      setAnalysisStages({
        stage1_forecast: response.stage1_forecast || null,
        stage2_zerocupon: response.stage2_zerocupon || null,
        stage3_bonds: response.stage3_bonds || null,
      });
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
            <Box sx={{ width: '300px', mr: 2 }}>
              <SearchFilter />
            </Box>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleRefreshRatingsClick}
              startIcon={
                isRefreshingRatings ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon />
              }
              disabled={isRefreshingRatings}
              sx={{ mr: 1 }}
            >
              Обновить рейтинги
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleRefreshEmitentsClick}
              startIcon={
                isRefreshingEmitents ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon />
              }
              disabled={isRefreshingEmitents}
              sx={{ mr: 1 }}
            >
              Обновить эмитентов
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleRefreshCouponsClick}
              startIcon={
                isRefreshingCoupons ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon />
              }
              disabled={isRefreshingCoupons}
              sx={{ mr: 1 }}
            >
              Обновить купоны
            </Button>
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
              startIcon={
                isAnalyzing ? <CircularProgress size={18} color="inherit" /> : <PsychologyIcon />
              }
              sx={{ mr: 1 }}
              disabled={isAnalyzing}
            >
              Отправить на анализ LLM
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleQwenAnalysisClick}
              startIcon={
                isQwenAnalyzing ? <CircularProgress size={18} color="inherit" /> : <PsychologyIcon />
              }
              disabled={isQwenAnalyzing}
              sx={{ mr: 1 }}
            >
              Отправить Qwen 3
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleGrokAnalysisClick}
              startIcon={
                isGrokAnalyzing ? <CircularProgress size={18} color="inherit" /> : <PsychologyIcon />
              }
              disabled={isGrokAnalyzing}
            >
              Отправить Grok 4.1 Fast
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ flexGrow: 1, bgcolor: 'background.default', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', width: '100%' }}>
        <Container maxWidth={false} sx={{ px: 2, py: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
          {/* Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
            <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
              <Tab label="Скринер облигаций" />
              <Tab label="Кривая бескупонной доходности" />
              <Tab label="Среднесрочный прогноз Банка России" />
              <Tab label="Мой портфель" />
            </Tabs>
          </Box>

          {/* Tab Content */}
          {currentTab === 0 && (
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 2, minHeight: 0, width: '100%' }}>
              {/* Filters Button - Above Table */}
              <Box sx={{ width: '100%', flexShrink: 0, display: 'flex', justifyContent: 'flex-start' }}>
                <Button
                  variant="outlined"
                  startIcon={<FilterAltIcon />}
                  onClick={() => setIsFiltersModalOpen(true)}
                  sx={{ mb: 1 }}
                >
                  Фильтры
                </Button>
              </Box>

              {/* Table - Full Width */}
              <Box sx={{ flexGrow: 1, minWidth: 0, width: '100%' }}>
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

          {currentTab === 3 && (
            <Box sx={{ flexGrow: 1, minHeight: 0 }}>
              <PortfolioTable />
            </Box>
          )}
        </Container>
      </Box>

      {/* Bond Details Drawer */}
      <BondDetails />

      {/* Filters Modal */}
      <FiltersModal
        open={isFiltersModalOpen}
        onClose={() => setIsFiltersModalOpen(false)}
      />

      {/* LLM Analysis Dialogs */}
      <AnalysisParamsDialog
        open={isAnalysisParamsOpen}
        onClose={() => setIsAnalysisParamsOpen(false)}
        onConfirm={handleAnalysisParamsConfirm}
      />
      
      {/* Qwen Analysis Dialogs */}
      <AnalysisParamsDialog
        open={isQwenParamsOpen}
        onClose={() => setIsQwenParamsOpen(false)}
        onConfirm={handleQwenAnalysisParamsConfirm}
      />
      
      {/* Grok Analysis Dialogs */}
      <AnalysisParamsDialog
        open={isGrokParamsOpen}
        onClose={() => setIsGrokParamsOpen(false)}
        onConfirm={handleGrokAnalysisParamsConfirm}
      />
      
      <AnalysisResultDialog
        open={isAnalysisResultOpen}
        onClose={() => setIsAnalysisResultOpen(false)}
        analysis={analysisResult}
        stages={analysisStages}
        isLoading={isAnalyzing || isQwenAnalyzing || isGrokAnalyzing}
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
