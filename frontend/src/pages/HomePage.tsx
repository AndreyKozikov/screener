import React, { useState, useRef } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Tabs, Tab, Dialog, DialogTitle, DialogContent, DialogActions, Alert } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FeedbackIcon from '@mui/icons-material/Feedback';
import { SearchFilter } from '../components/filters/SearchFilter';
import { FiltersModal } from '../components/filters/FiltersModal';
import { BondsTable } from '../components/bonds/BondsTable';
import { BondDetails } from '../components/bonds/BondDetails';
import { ZerocuponTable } from '../components/zerocupon/ZerocuponTable';
import { ForecastTable } from '../components/forecast/ForecastTable';
import { PortfolioTable } from '../components/portfolio/PortfolioTable';
import { ComparisonTable } from '../components/bonds/ComparisonTable';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { LLMAnalysisModelDialog, type LLMModel } from '../components/llm/LLMAnalysisModelDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { BondSelectionGuidePage } from './BondSelectionGuidePage';
import { RefreshDataDialog } from '../components/common/RefreshDataDialog';
import { FeedbackDialog } from '../components/common/FeedbackDialog';
import { refreshBondsData, refreshCouponsData } from '../api/bonds';
import { refreshZerocuponData } from '../api/zerocupon';
import { refreshRatingsData } from '../api/rating';
import { refreshEmitentsData } from '../api/emitent';
import { useUiStore } from '../stores/uiStore';
import { useBondsStore } from '../stores/bondsStore';
import { useComparisonStore } from '../stores/comparisonStore';
import { getBondsDataForLLM, getZerocuponDataForLLM, getForecastDataForLLM } from '../utils/llmDataExport';
import { analyzeBondsWithLLM } from '../api/llm';
import { analyzeBondsWithQwen } from '../api/qwen';
import { analyzeBondsWithGrok } from '../api/grok';
import { submitFeedback } from '../api/feedback';

/**
 * HomePage Component
 * 
 * Main page of the application displaying bonds screener
 */
export const HomePage: React.FC = () => {
  const triggerDataRefresh = useUiStore((state) => state.triggerDataRefresh);
  const setError = useBondsStore((state) => state.setError);
  const comparisonBonds = useComparisonStore((state) => state.comparisonBonds);
  const [currentTab, setCurrentTab] = useState(0);
  
  // Refresh data dialog state
  const [isRefreshDialogOpen, setIsRefreshDialogOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<Record<string, { status: 'idle' | 'loading' | 'success' | 'error'; error?: string }>>({});
  
  // LLM Analysis state
  const [isAnalysisParamsOpen, setIsAnalysisParamsOpen] = useState(false);
  const [isLLMModelDialogOpen, setIsLLMModelDialogOpen] = useState(false);
  const [, setSelectedLLMModel] = useState<LLMModel | null>(null);
  const [savedAnalysisParams, setSavedAnalysisParams] = useState<{
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
    includeZerocupon: boolean;
    includeForecast: boolean;
  } | null>(null);
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
  const [isFiltersModalOpen, setIsFiltersModalOpen] = useState(false);
  const [isFeedbackDialogOpen, setIsFeedbackDialogOpen] = useState(false);

  const handleRefreshDataClick = () => {
    setIsRefreshDialogOpen(true);
  };

  const handleRefreshConfirm = async (selectedTasks: string[]) => {
    if (selectedTasks.length === 0) {
      return;
    }

    setIsRefreshing(true);
    setError(null);
    
    // Initialize status for all selected tasks
    const initialStatus: Record<string, { status: 'idle' | 'loading' | 'success' | 'error'; error?: string }> = {};
    selectedTasks.forEach(taskId => {
      initialStatus[taskId] = { status: 'loading' };
    });
    setRefreshStatus(initialStatus);

    // Define task handlers
    const taskHandlers: Record<string, () => Promise<void>> = {
      bonds: async () => {
        await refreshBondsData();
        // Also refresh zero-coupon yield curve data as part of bonds refresh
        try {
          await refreshZerocuponData();
        } catch (zerocuponError) {
          console.error('Failed to refresh zerocupon data', zerocuponError);
          // Don't fail the whole refresh if zerocupon update fails
        }
        triggerDataRefresh();
      },
      ratings: async () => {
        await refreshRatingsData();
      },
      emitents: async () => {
        await refreshEmitentsData();
      },
      coupons: async () => {
        await refreshCouponsData();
      },
    };

    // Execute all selected tasks in parallel
    const promises = selectedTasks.map(async (taskId) => {
      const handler = taskHandlers[taskId];
      if (!handler) {
        setRefreshStatus(prev => ({
          ...prev,
          [taskId]: { status: 'error', error: 'Неизвестная задача' },
        }));
        return;
      }

      try {
        await handler();
        setRefreshStatus(prev => ({
          ...prev,
          [taskId]: { status: 'success' },
        }));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Неизвестная ошибка';
        console.error(`Failed to refresh ${taskId}`, error);
        setRefreshStatus(prev => ({
          ...prev,
          [taskId]: { status: 'error', error: errorMessage },
        }));
      }
    });

    // Wait for all tasks to complete
    await Promise.allSettled(promises);
    
    setIsRefreshing(false);
  };

  const handleLLMAnalysisClick = () => {
    // Note: LLM analysis functionality needs to be updated to use comparison bonds or all bonds
    // For now, show message that selection is needed via comparison table
    setIsNoSelectionDialogOpen(true);
  };

  const handleAnalysisParamsConfirm = (params: {
    zerocuponDateFrom: string;
    zerocuponDateTo: string;
    forecastDate: string;
    includeZerocupon: boolean;
    includeForecast: boolean;
  }) => {
    // Save parameters and open model selection dialog
    setSavedAnalysisParams(params);
    setIsAnalysisParamsOpen(false);
    setIsLLMModelDialogOpen(true);
  };

  const handleLLMModelSelect = async (model: LLMModel) => {
    if (!savedAnalysisParams) {
      return;
    }

    setSelectedLLMModel(model);
    setIsLLMModelDialogOpen(false);
    
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
      // Use comparison bonds for LLM analysis
      if (comparisonBonds.length === 0) {
        setIsNoSelectionDialogOpen(true);
        return;
      }

      const params = savedAnalysisParams;
      const selectedBonds = new Set(comparisonBonds.map(bond => bond.SECID).filter((secid): secid is string => !!secid));

      // Step 1: Load data files conditionally based on checkboxes
      const modelPrefix = model.toUpperCase();
      console.log(`[${modelPrefix}] Step 1: Loading data files...`);
      const bondsData = await getBondsDataForLLM(Array.from(selectedBonds));
      
      let zerocuponData = '';
      let forecastData = '';
      
      if (params.includeZerocupon) {
        zerocuponData = await getZerocuponDataForLLM(params.zerocuponDateFrom, params.zerocuponDateTo);
      }
      if (params.includeForecast) {
        forecastData = await getForecastDataForLLM(params.forecastDate);
      }
      
      console.log(`[${modelPrefix}] Step 1 complete: Data files loaded`);
      console.log(`[${modelPrefix}] Bonds data size: ${bondsData.length} chars`);
      if (params.includeZerocupon) {
        console.log(`[${modelPrefix}] Zerocupon data size: ${zerocuponData.length} chars`);
      }
      if (params.includeForecast) {
        console.log(`[${modelPrefix}] Forecast data size: ${forecastData.length} chars`);
      }

      // Step 2: Send loaded data to selected model
      let response;
      if (model === 'llm') {
        console.log(`[${modelPrefix}] Step 2: Sending data to LLM as files...`);
        console.log(`[${modelPrefix}] This may take several minutes. Please wait...`);
        response = await analyzeBondsWithLLM(
          bondsData,
          zerocuponData,
          forecastData,
          'gpt-5.1',
          params.includeZerocupon,
          params.includeForecast
        );
      } else if (model === 'qwen') {
        console.log(`[${modelPrefix}] Step 2: Sending data to Qwen 3 via OpenRouter as files...`);
        console.log(`[${modelPrefix}] This may take several minutes. Please wait...`);
        response = await analyzeBondsWithQwen(
          bondsData,
          zerocuponData,
          forecastData,
          'qwen/qwen3-235b-a22b:free',
          params.includeZerocupon,
          params.includeForecast
        );
      } else if (model === 'grok') {
        console.log(`[${modelPrefix}] Step 2: Sending data to Grok 4.1 Fast via OpenRouter as files...`);
        console.log(`[${modelPrefix}] This may take several minutes. Please wait...`);
        response = await analyzeBondsWithGrok(
          bondsData,
          zerocuponData,
          forecastData,
          'x-ai/grok-4.1-fast:free',
          params.includeZerocupon,
          params.includeForecast
        );
      } else {
        throw new Error('Неизвестная модель');
      }

      setAnalysisResult(response.analysis);
      setAnalysisStages({
        stage1_forecast: response.stage1_forecast || null,
        stage2_zerocupon: response.stage2_zerocupon || null,
        stage3_bonds: response.stage3_bonds || null,
      });
      setModelUsed(response.model_used);
      setIsAnalysisResultOpen(true);
    } catch (error) {
      console.error(`Error during ${model} analysis:`, error);
      const errorMessages: Record<LLMModel, string> = {
        llm: 'Не удалось выполнить анализ',
        qwen: 'Не удалось выполнить анализ Qwen 3',
        grok: 'Не удалось выполнить анализ Grok 4.1 Fast',
      };
      setAnalysisError(
        error instanceof Error ? error.message : errorMessages[model]
      );
      setIsAnalysisResultOpen(true);
    } finally {
      setIsAnalyzing(false);
      setSelectedLLMModel(null);
      setSavedAnalysisParams(null);
    }
  };

  // Get current tab name
  const getCurrentTabName = (): string => {
    const tabNames = [
      'Скринер облигаций',
      'Кривая бескупонной доходности',
      'Среднесрочный прогноз Банка России',
      'Мой портфель',
      'Сравнение облигаций',
      'Советы по выбору облигаций',
    ];
    return tabNames[currentTab] || 'Неизвестная вкладка';
  };

  const handleFeedbackClick = () => {
    setIsFeedbackDialogOpen(true);
  };

  const handleFeedbackSend = async (text: string, tabName: string) => {
    await submitFeedback(text, tabName);
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
              onClick={handleRefreshDataClick}
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
              Анализ LLM
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              onClick={handleFeedbackClick}
              startIcon={<FeedbackIcon />}
              sx={{ mr: 1 }}
            >
              Предложения
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ flexGrow: 1, bgcolor: 'background.default', display: 'flex', flexDirection: 'column', width: '100%', ...(currentTab !== 5 ? { height: 'calc(100vh - 64px)' } : {}) }}>
        {currentTab === 5 ? (
          <>
            {/* Tabs for course tab */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, px: 2, pt: 2 }}>
              <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
                <Tab label="Скринер облигаций" />
                <Tab label="Кривая бескупонной доходности" />
                <Tab label="Среднесрочный прогноз Банка России" />
                <Tab label="Мой портфель" />
                <Tab label="Сравнение облигаций" />
                <Tab label="Советы по выбору облигаций" />
              </Tabs>
            </Box>
            {/* Course content without Container */}
            <Box sx={{ flexGrow: 1, minHeight: 0, width: '100%' }}>
              <BondSelectionGuidePage />
            </Box>
          </>
        ) : (
          <Container maxWidth={false} sx={{ px: 2, py: 2, flexGrow: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
            {/* Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)}>
                <Tab label="Скринер облигаций" />
                <Tab label="Кривая бескупонной доходности" />
                <Tab label="Среднесрочный прогноз Банка России" />
                <Tab label="Мой портфель" />
                <Tab label="Сравнение облигаций" />
                <Tab label="Советы по выбору облигаций" />
              </Tabs>
            </Box>

            {/* Tab Content */}
            {currentTab === 0 && (
              <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 2, minHeight: 0, width: '100%' }}>
                {/* Table - Full Width */}
                <Box sx={{ flexGrow: 1, minWidth: 0, width: '100%' }}>
                  <ErrorBoundary>
                    <BondsTable 
                      onOpenFilters={() => setIsFiltersModalOpen(true)}
                    />
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

            {currentTab === 4 && (
              <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                <ComparisonTable />
              </Box>
            )}
          </Container>
        )}
      </Box>

      {/* Bond Details Drawer */}
      <BondDetails />

      {/* Filters Modal */}
      <FiltersModal
        open={isFiltersModalOpen}
        onClose={() => setIsFiltersModalOpen(false)}
      />

      {/* Refresh Data Dialog */}
      <RefreshDataDialog
        open={isRefreshDialogOpen}
        onClose={() => {
          if (!isRefreshing) {
            setIsRefreshDialogOpen(false);
            // Reset status when closing
            setRefreshStatus({});
          }
        }}
        onConfirm={handleRefreshConfirm}
        tasks={[
          { id: 'bonds', label: 'Обновить данные облигаций', checked: false },
          { id: 'ratings', label: 'Обновить рейтинги', checked: false },
          { id: 'emitents', label: 'Обновить эмитентов', checked: false },
          { id: 'coupons', label: 'Обновить купоны', checked: false },
        ]}
        isRefreshing={isRefreshing}
        refreshStatus={refreshStatus}
      />

      {/* LLM Analysis Parameters Dialog - First step */}
      <AnalysisParamsDialog
        open={isAnalysisParamsOpen}
        onClose={() => {
          setIsAnalysisParamsOpen(false);
          setSavedAnalysisParams(null);
        }}
        onConfirm={handleAnalysisParamsConfirm}
      />

      {/* LLM Model Selection Dialog - Second step */}
      <LLMAnalysisModelDialog
        open={isLLMModelDialogOpen}
        onClose={() => {
          setIsLLMModelDialogOpen(false);
          setSavedAnalysisParams(null);
        }}
        onConfirm={handleLLMModelSelect}
      />
      
      {/* LLM Analysis Result Dialog */}
      <AnalysisResultDialog
        open={isAnalysisResultOpen}
        onClose={() => setIsAnalysisResultOpen(false)}
        analysis={analysisResult}
        stages={analysisStages}
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

      {/* Feedback Dialog */}
      <FeedbackDialog
        open={isFeedbackDialogOpen}
        onClose={() => setIsFeedbackDialogOpen(false)}
        onSend={handleFeedbackSend}
        tabName={getCurrentTabName()}
      />

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
