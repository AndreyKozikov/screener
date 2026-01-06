import React, { useState, useEffect } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions, Alert, IconButton, Card, CardContent, alpha } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FeedbackIcon from '@mui/icons-material/Feedback';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import TimelineIcon from '@mui/icons-material/Timeline';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SchoolIcon from '@mui/icons-material/School';
import { FiltersModal } from '../components/filters/FiltersModal';
import { BondsTable } from '../components/bonds/BondsTable';
import { BondDetails } from '../components/bonds/BondDetails';
import { ZerocuponTable } from '../components/zerocupon/ZerocuponTable';
import { ForecastTable } from '../components/forecast/ForecastTable';
import { Workbench } from '../components/portfolio/Workbench';
import { HubCard } from '../components/portfolio/HubCard';
import { ComparisonTable } from '../components/bonds/ComparisonTable';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { LLMAnalysisModelDialog, type LLMModel } from '../components/llm/LLMAnalysisModelDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { RefreshDataDialog } from '../components/common/RefreshDataDialog';
import { FeedbackDialog } from '../components/common/FeedbackDialog';
import { BondSelectionGuidePage } from './BondSelectionGuidePage';
import { refreshBondsData, refreshCouponsData } from '../api/bonds';
import { refreshZerocuponData } from '../api/zerocupon';
import { refreshRatingsData } from '../api/rating';
import { refreshEmitentsData } from '../api/emitent';
import { getCurrencyRates, refreshCurrencyRates, type CurrencyRatesResponse } from '../api/currency';
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
type ViewMode = 'HUB' | 'TABLE';

export const HomePage: React.FC = () => {
  const triggerDataRefresh = useUiStore((state) => state.triggerDataRefresh);
  const setError = useBondsStore((state) => state.setError);
  const comparisonBonds = useComparisonStore((state) => state.comparisonBonds);
  const [viewMode, setViewMode] = useState<ViewMode>('HUB');
  const [currentTab, setCurrentTab] = useState(0);
  const [forecastSubView, setForecastSubView] = useState<'zerocupon' | 'forecast' | null>(null);
  
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
  
  // Currency rates state
  const [currencyRates, setCurrencyRates] = useState<CurrencyRatesResponse | null>(null);
  const [isLoadingCurrencyRates, setIsLoadingCurrencyRates] = useState(false);

  // Load currency rates on mount
  useEffect(() => {
    const loadCurrencyRates = async () => {
      setIsLoadingCurrencyRates(true);
      try {
        const rates = await getCurrencyRates();
        setCurrencyRates(rates);
      } catch (error) {
        console.error('Failed to load currency rates:', error);
      } finally {
        setIsLoadingCurrencyRates(false);
      }
    };
    
    loadCurrencyRates();
  }, []);

  const handleRefreshDataClick = () => {
    setIsRefreshDialogOpen(true);
  };

  const handleRefreshConfirm = async (selectedTasks: string[], forceUpdateRatings?: boolean) => {
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
        triggerDataRefresh();
      },
      zerocupon: async () => {
        await refreshZerocuponData();
      },
      ratings: async () => {
        await refreshRatingsData(forceUpdateRatings || false);
      },
      emitents: async () => {
        await refreshEmitentsData();
      },
      coupons: async () => {
        await refreshCouponsData();
      },
      currency: async () => {
        await refreshCurrencyRates();
        // Reload currency rates to update display
        try {
          const rates = await getCurrencyRates();
          setCurrencyRates(rates);
        } catch (error) {
          console.error('Failed to reload currency rates:', error);
        }
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
    ];
    return tabNames[currentTab] || 'Центр управления';
  };

  const handleFeedbackClick = () => {
    setIsFeedbackDialogOpen(true);
  };

  const handleFeedbackSend = async (text: string, tabName: string) => {
    await submitFeedback(text, tabName);
  };

  const handleHubCardClick = (tabIndex: number) => {
    setCurrentTab(tabIndex);
    setViewMode('TABLE');
    // Если выбрана карточка "Прогнозы", сбросить подраздел
    if (tabIndex === 2) {
      setForecastSubView(null);
    }
  };

  const handleBackToHub = () => {
    setViewMode('HUB');
  };

  // Hub Cards Configuration
  const hubCards = [
    {
      title: 'Рынок Облигаций',
      description: 'Поиск и фильтрация активов',
      icon: <ShowChartIcon sx={{ fontSize: 48 }} />,
      color: '#1976d2',
      onClick: () => handleHubCardClick(0),
    },
    {
      title: 'Мой Портфель',
      description: 'Управление инвестициями',
      icon: <AccountBalanceWalletIcon sx={{ fontSize: 48 }} />,
      color: '#4caf50',
      onClick: () => handleHubCardClick(3),
    },
    {
      title: 'Прогнозы',
      description: 'Анализ и прогнозирование',
      icon: <TrendingUpIcon sx={{ fontSize: 48 }} />,
      color: '#ff9800',
      onClick: () => handleHubCardClick(2),
    },
    {
      title: 'Сравнение',
      description: 'Сопоставление облигаций',
      icon: <CompareArrowsIcon sx={{ fontSize: 48 }} />,
      color: '#9c27b0',
      onClick: () => handleHubCardClick(4),
    },
    {
      title: 'Советы по выбору',
      description: 'Пошаговое руководство по отбору облигаций',
      icon: <SchoolIcon sx={{ fontSize: 48 }} />,
      color: '#00acc1',
      onClick: () => handleHubCardClick(5),
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: '#F8FAFC' }}>
      {/* Compact App Bar */}
      <AppBar 
        position="static" 
        elevation={0}
        sx={{
          bgcolor: 'transparent',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Toolbar sx={{ minHeight: '32px !important', py: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <AccountBalanceIcon sx={{ fontSize: 20, color: 'text.primary' }} />
              <Typography 
                variant="body1" 
                component="h1" 
                fontWeight={600}
                sx={{
                  fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  letterSpacing: '-0.01em',
                  fontSize: '0.875rem',
                }}
              >
                Центр Управления
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <IconButton
                size="small"
                onClick={handleRefreshDataClick}
                disabled={isRefreshing}
                sx={{ 
                  color: 'text.primary',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                {isRefreshing ? (
                  <CircularProgress size={18} />
                ) : (
                  <RefreshIcon sx={{ fontSize: 18 }} />
                )}
              </IconButton>
              <IconButton
                size="small"
                onClick={handleLLMAnalysisClick}
                disabled={isAnalyzing}
                sx={{ 
                  color: 'text.primary',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                {isAnalyzing ? (
                  <CircularProgress size={18} />
                ) : (
                  <PsychologyIcon sx={{ fontSize: 18 }} />
                )}
              </IconButton>
              <IconButton
                size="small"
                onClick={handleFeedbackClick}
                sx={{ 
                  color: 'text.primary',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <FeedbackIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Box>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ 
        flexGrow: 1, 
        bgcolor: '#F8FAFC', 
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%', 
        ...(viewMode === 'TABLE' ? { height: 'calc(100vh - 32px)' } : {}) 
      }}>
        {viewMode === 'HUB' ? (
          <>
            {/* Currency Rates */}
            <Box
              sx={{
                bgcolor: 'background.paper',
                border: '1px solid #E2E8F0',
                borderRadius: '16px',
                px: 3,
                py: 1.5,
                mx: 'auto',
                mt: 4,
                mb: 3,
                width: 'fit-content',
                display: 'flex',
                gap: 4,
                alignItems: 'center',
                boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.05)',
              }}
            >
              {isLoadingCurrencyRates ? (
                <CircularProgress size={16} />
              ) : currencyRates ? (
                (() => {
                  const currencies = [
                    currencyRates.rates.EUR && { code: 'EUR', rate: currencyRates.rates.EUR.rate },
                    currencyRates.rates.USD && { code: 'USD', rate: currencyRates.rates.USD.rate },
                    currencyRates.rates.CNY && { code: 'CNY', rate: currencyRates.rates.CNY.rate },
                  ].filter(Boolean) as Array<{ code: string; rate: number }>;
                  
                  return currencies.map((currency, index) => (
                    <React.Fragment key={currency.code}>
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          color: 'text.primary',
                        }}
                      >
                        {currency.code}: <strong>{currency.rate.toFixed(2)}</strong>
                      </Typography>
                      {index < currencies.length - 1 && (
                        <Box
                          sx={{
                            width: '1px',
                            height: '16px',
                            bgcolor: 'divider',
                          }}
                        />
                      )}
                    </React.Fragment>
                  ));
                })()
              ) : (
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    fontSize: '0.75rem',
                    fontWeight: 500,
                    color: 'text.secondary',
                  }}
                >
                  Курсы валют не загружены
                </Typography>
              )}
            </Box>

            {/* Hub Cards Grid */}
            <Box
              sx={{
                width: '100%',
                px: 3,
                mb: 4,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: { xs: 'column', sm: 'row' },
                  gap: 3,
                  width: '100%',
                }}
              >
                {hubCards.map((card, index) => (
                  <Card
                    key={index}
                    onClick={card.onClick}
                    sx={{
                      flex: 1,
                      minWidth: 0,
                      height: 220,
                      borderRadius: '16px',
                      border: '1px solid #E2E8F0',
                      bgcolor: 'background.paper',
                      cursor: 'pointer',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: 'none',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0px 8px 24px rgba(0, 0, 0, 0.08)',
                        '& .hub-card-icon': {
                          transform: 'scale(1.1)',
                        },
                      },
                    }}
                  >
                    <CardContent
                      sx={{
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        p: 3,
                      }}
                    >
                      <Box
                        className="hub-card-icon"
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: 64,
                          height: 64,
                          borderRadius: '16px',
                          bgcolor: alpha(card.color, 0.1),
                          color: card.color,
                          mb: 2,
                          transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                        }}
                      >
                        {card.icon}
                      </Box>
                      <Box>
                        <Typography
                          variant="h6"
                          sx={{
                            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                            fontWeight: 600,
                            fontSize: '1.25rem',
                            mb: 1,
                            letterSpacing: '-0.01em',
                            color: 'text.primary',
                          }}
                        >
                          {card.title}
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                            color: 'text.secondary',
                            fontSize: '0.875rem',
                          }}
                        >
                          {card.description}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            </Box>
          </>
        ) : (
          <Container 
            maxWidth={false} 
            sx={{ 
              px: 2, 
              py: 3, 
              flexGrow: 1, 
              display: 'flex', 
              flexDirection: 'column', 
              width: '100%',
              bgcolor: 'grey.50',
            }}
          >
            {/* Back Button */}
            <Box sx={{ 
              display: 'flex',
              alignItems: 'center',
              mb: 2,
            }}>
              <Button
                startIcon={<ArrowBackIcon />}
                onClick={handleBackToHub}
                variant="text"
                size="small"
                sx={{
                  textTransform: 'none',
                  fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  fontSize: '0.875rem',
                  color: 'text.secondary',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                Назад в центр управления
              </Button>
            </Box>

            {/* Tab Content */}
            {currentTab === 0 && (
              <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 2, minHeight: 0, width: '100%' }}>
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
              <>
                {forecastSubView === null ? (
                  // Forecast Selection Screen
                  <Box
                    sx={{
                      width: '100%',
                      p: 3,
                    }}
                  >
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 3 }}>
                      <HubCard
                        title="Кривая бескупонной доходности"
                        value="—"
                        subtitle="Анализ временной структуры процентных ставок на основе данных Мосбиржи"
                        icon={<TimelineIcon />}
                        color="#1976d2"
                        onClick={() => setForecastSubView('zerocupon')}
                      />
                      <HubCard
                        title="Среднесрочный прогноз Банка России"
                        value="—"
                        subtitle="Основные показатели денежно-кредитной политики и макроэкономические ожидания регулятора"
                        icon={<AssessmentIcon />}
                        color="#ff9800"
                        onClick={() => setForecastSubView('forecast')}
                      />
                    </Box>
                  </Box>
                ) : (
                  // Forecast Content
                  <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    {/* Back Button */}
                    <Box sx={{ 
                      display: 'flex',
                      alignItems: 'center',
                      mb: 2,
                      px: 2,
                    }}>
                      <Button
                        startIcon={<ArrowBackIcon />}
                        onClick={() => setForecastSubView(null)}
                        variant="text"
                        size="small"
                        sx={{
                          textTransform: 'none',
                          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          fontSize: '0.875rem',
                          color: 'text.secondary',
                          '&:hover': {
                            bgcolor: 'action.hover',
                          },
                        }}
                      >
                        Назад к выбору прогнозов
                      </Button>
                    </Box>
                    
                    {/* Forecast Content */}
                    {forecastSubView === 'zerocupon' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <ZerocuponTable />
                      </Box>
                    )}
                    
                    {forecastSubView === 'forecast' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <ForecastTable />
                      </Box>
                    )}
                  </Box>
                )}
              </>
            )}

            {currentTab === 3 && (
              <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                <Workbench />
              </Box>
            )}

            {currentTab === 4 && (
              <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                <ComparisonTable />
              </Box>
            )}

            {currentTab === 5 && (
              <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                <BondSelectionGuidePage />
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
          { id: 'zerocupon', label: 'Обновление данных кривой бескупонной доходности', checked: false },
          { id: 'ratings', label: 'Обновить рейтинги', checked: false },
          { id: 'emitents', label: 'Обновить эмитентов', checked: false },
          { id: 'coupons', label: 'Обновить купоны', checked: false },
          { id: 'currency', label: 'Обновить курсы валют', checked: false },
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
        PaperProps={{
          sx: {
            borderRadius: '20px',
            border: '1px solid #E2E8F0',
          },
        }}
      >
        <DialogTitle>Не выбраны облигации</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            Для отправки на анализ LLM необходимо выбрать хотя бы одну облигацию в таблице.
            Пожалуйста, выберите одну или несколько облигаций и попробуйте снова.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setIsNoSelectionDialogOpen(false)} 
            variant="contained" 
            autoFocus
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            }}
          >
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
    </Box>
  );
};

export default HomePage;
