import React, { useState, useEffect } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions, Alert, IconButton, Card, CardContent, alpha } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FeedbackIcon from '@mui/icons-material/Feedback';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import TimelineIcon from '@mui/icons-material/Timeline';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import PercentIcon from '@mui/icons-material/Percent';
import ArticleIcon from '@mui/icons-material/Article';
import { FiltersModal } from '../components/filters/FiltersModal';
import { BondsTable } from '../components/bonds/BondsTable';
import { BondDetails } from '../components/bonds/BondDetails';
import { ZerocuponTable } from '../components/zerocupon/ZerocuponTable';
import { ForecastTable } from '../components/forecast/ForecastTable';
import { RuoniaTable } from '../components/ruonia/RuoniaTable';
import { KeyRateTable } from '../components/keyrate/KeyRateTable';
import { Workbench } from '../components/portfolio/Workbench';
import { HubCard } from '../components/portfolio/HubCard';
import { ComparisonTable } from '../components/bonds/ComparisonTable';
import { SpreadAnalysis } from '../components/bonds/SpreadAnalysis';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { LLMAnalysisModelDialog, type LLMModel } from '../components/llm/LLMAnalysisModelDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { RefreshDataDialog } from '../components/common/RefreshDataDialog';
import { ForecastFileDialog } from '../components/common/ForecastFileDialog';
import { FeedbackDialog } from '../components/common/FeedbackDialog';
import { HelpDialog, type HelpSection } from '../components/common/HelpDialog';
import { BlogPage } from './BlogPage';
import { refreshBondsData, refreshCouponsData } from '../api/bonds';
import { refreshFloatersData } from '../api/edisclosure';
import { refreshZerocuponData, fetchZerocuponData } from '../api/zerocupon';
import { refreshRatingsData } from '../api/rating';
import { refreshRuoniaData } from '../api/ruonia';
import { fetchForecastDates, uploadForecastMd } from '../api/forecast';
import { refreshEmitentsData } from '../api/emitent';
import { refreshTradingHistory } from '../api/tradingHistory';
import { getDashboardRates, type MacroRatesResponse } from '../api/dashboard';
import { refreshCurrencyRates } from '../api/currency';
import { loadKeyRateData } from '../api/keyrate';
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
  const [forecastSubView, setForecastSubView] = useState<'zerocupon' | 'forecast' | 'ruonia' | 'keyrate' | null>(null);
  const [comparisonSubView, setComparisonSubView] = useState<'comparison' | 'spread-analysis' | null>(null);
  
  // Refresh data dialog state
  const [isRefreshDialogOpen, setIsRefreshDialogOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<Record<string, { status: 'idle' | 'loading' | 'success' | 'error'; error?: string }>>({});
  // Forecast file dialog: when user selects "forecast" and clicks Обновить, open file picker before running refresh
  const [isForecastFileDialogOpen, setIsForecastFileDialogOpen] = useState(false);
  const [pendingRefreshTasks, setPendingRefreshTasks] = useState<string[]>([]);
  const [pendingForceUpdateRatings, setPendingForceUpdateRatings] = useState(false);
  const [pendingForceRefreshCoupons, setPendingForceRefreshCoupons] = useState(false);
  
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
  const [isHelpDialogOpen, setIsHelpDialogOpen] = useState(false);
  
  // Dashboard rates (currency, RUONIA, key rate) — один ответ с бэкенда, отображаем как есть
  const [dashboardRates, setDashboardRates] = useState<MacroRatesResponse | null>(null);
  const [isLoadingDashboardRates, setIsLoadingDashboardRates] = useState(false);

  // Forecast cards last dates state
  const [zerocuponLastDate, setZerocuponLastDate] = useState<string | null>(null);
  const [forecastLastDate, setForecastLastDate] = useState<string | null>(null);
  /** Список дат прогнозов (YYYY-MM-DD), загружается при входе в комнату «Прогнозы», передаётся в ForecastTable чтобы не дублировать запрос */
  const [availableForecastDates, setAvailableForecastDates] = useState<string[] | null>(null);

  // Helper function to format date from DD.MM.YYYY or YYYY-MM-DD to DD.MM.YYYY
  const formatDateForDisplay = (dateStr: string | null): string | null => {
    if (!dateStr) return null;
    
    // If already in DD.MM.YYYY format, return as is
    if (/^\d{2}\.\d{2}\.\d{4}$/.test(dateStr)) {
      return dateStr;
    }
    
    // If in YYYY-MM-DD format, convert to DD.MM.YYYY
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [year, month, day] = dateStr.split('-');
      return `${day}.${month}.${year}`;
    }
    
    return dateStr;
  };

  // Загрузка данных плашки (курсы валют, RUONIA, ключевая ставка) одним запросом
  useEffect(() => {
    const loadDashboardRates = async () => {
      setIsLoadingDashboardRates(true);
      try {
        const data = await getDashboardRates();
        setDashboardRates(data);
      } catch (error) {
        console.error('Failed to load dashboard rates:', error);
      } finally {
        setIsLoadingDashboardRates(false);
      }
    };
    loadDashboardRates();
  }, []);

  // Load last dates for zerocupon card (once on mount)
  useEffect(() => {
    const loadZerocuponLastDate = async () => {
      try {
        const zerocuponData = await fetchZerocuponData(null, null);
        if (zerocuponData.data && zerocuponData.data.length > 0) {
          const firstRecord = zerocuponData.data[0];
          const dateStr = firstRecord['Дата'];
          setZerocuponLastDate(formatDateForDisplay(dateStr));
        }
      } catch (error) {
        console.error('Failed to load zerocupon last date:', error);
      }
    };
    loadZerocuponLastDate();
  }, []);

  // Запрос дат среднесрочных прогнозов при переходе в комнату «Прогнозы» (один раз; список передаётся в ForecastTable)
  useEffect(() => {
    if (currentTab !== 2) return;
    const loadForecastDates = async () => {
      try {
        const forecastDates = await fetchForecastDates();
        setAvailableForecastDates(forecastDates ?? []);
        if (forecastDates && forecastDates.length > 0) {
          setForecastLastDate(formatDateForDisplay(forecastDates[0]));
        } else {
          setForecastLastDate(null);
        }
      } catch (error) {
        console.error('Failed to load forecast dates:', error);
        setAvailableForecastDates([]);
        setForecastLastDate(null);
      }
    };
    void loadForecastDates();
  }, [currentTab]);

  const handleRefreshDataClick = () => {
    setIsRefreshDialogOpen(true);
  };

  const handleRefreshConfirm = async (
    selectedTasks: string[],
    forceUpdateRatings?: boolean,
    forceRefreshCoupons?: boolean,
    forecastFile?: File | null,
    floatersProvider?: string,
  ) => {
    if (selectedTasks.length === 0) {
      return;
    }

    // If forecast is selected but no file yet — open file selection dialog first
    if (selectedTasks.includes('forecast') && forecastFile === undefined) {
      setPendingRefreshTasks(selectedTasks);
      setPendingForceUpdateRatings(forceUpdateRatings ?? false);
      setPendingForceRefreshCoupons(forceRefreshCoupons ?? false);
      setIsForecastFileDialogOpen(true);
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

    const forecastFileRef = forecastFile ?? null;

    // Define task handlers
    const taskHandlers: Record<string, () => Promise<void>> = {
      bonds: async () => {
        await refreshBondsData();
        triggerDataRefresh();
      },
      zerocupon: async () => {
        // Pass update_zero_coupon_curve=true to update database after file save
        await refreshZerocuponData(true);
        // Reload last date after refresh
        try {
          const zerocuponData = await fetchZerocuponData(null, null);
          if (zerocuponData.data && zerocuponData.data.length > 0) {
            const firstRecord = zerocuponData.data[0];
            const dateStr = firstRecord['Дата'];
            setZerocuponLastDate(formatDateForDisplay(dateStr));
          }
        } catch (error) {
          console.error('Failed to reload zerocupon last date:', error);
        }
      },
      ratings: async () => {
        await refreshRatingsData(forceUpdateRatings || false);
      },
      emitents: async () => {
        await refreshEmitentsData();
      },
      coupons: async () => {
        await refreshCouponsData(forceRefreshCoupons || false);
      },
      currency: async () => {
        await refreshCurrencyRates();
      },
      ruonia: async () => {
        await refreshRuoniaData();
      },
      'trading-history': async () => {
        await refreshTradingHistory();
      },
      keyrate: async () => {
        await loadKeyRateData();
      },
      forecast: async () => {
        if (forecastFileRef) {
          await uploadForecastMd(forecastFileRef);
        }
      },
      floaters: async () => {
        await refreshFloatersData(floatersProvider ?? 'gemini');
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

    // Обновить плашку одним запросом, если обновляли курсы/RUONIA/ключевую ставку
    const panelTasks = ['currency', 'ruonia', 'keyrate'];
    if (selectedTasks.some((id) => panelTasks.includes(id))) {
      try {
        const data = await getDashboardRates();
        setDashboardRates(data);
      } catch (error) {
        console.error('Failed to reload dashboard rates:', error);
      }
    }

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
    // Если выбрана карточка "Сравнение", сбросить подраздел
    if (tabIndex === 4) {
      setComparisonSubView(null);
    }
  };

  const handleBackToHub = () => {
    setViewMode('HUB');
  };

  // Determine current help section based on view state
  const getCurrentHelpSection = (): HelpSection => {
    if (viewMode === 'HUB') {
      return 'default';
    }

    // Determine section based on currentTab and subviews
    if (currentTab === 0) {
      // Рынок Облигаций
      return 'bonds-table';
    } else if (currentTab === 2) {
      // Прогнозы
      if (forecastSubView === 'zerocupon') {
        return 'zerocupon';
      } else if (forecastSubView === 'forecast') {
        return 'forecast';
      } else if (forecastSubView === 'ruonia') {
        return 'ruonia';
      } else if (forecastSubView === 'keyrate') {
        return 'keyrate';
      }
      return 'default';
    } else if (currentTab === 3) {
      // Мой Портфель
      return 'portfolio';
    } else if (currentTab === 4) {
      // Сравнение
      if (comparisonSubView === 'comparison') {
        return 'comparison-bonds';
      } else if (comparisonSubView === 'spread-analysis') {
        return 'spread-analysis';
      }
      return 'default';
    }

    return 'default';
  };

  const handleHelpClick = () => {
    setIsHelpDialogOpen(true);
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
      title: 'Блог',
      description: 'Статьи и интерактивный гид по облигациям',
      icon: <ArticleIcon sx={{ fontSize: 48 }} />,
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
              <IconButton
                size="small"
                onClick={handleHelpClick}
                sx={{ 
                  color: 'text.primary',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <HelpOutlineIcon sx={{ fontSize: 18 }} />
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
            {/* Плашка: курсы валют, RUONIA, ключевая ставка — данные с одного эндпоинта, отображаем как есть */}
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
              {isLoadingDashboardRates ? (
                <CircularProgress size={16} />
              ) : (
                (() => {
                  const dr = dashboardRates;
                  const currencies = dr?.rates
                    ? [
                        dr.rates.EUR && { label: 'EUR', value: dr.rates.EUR.rate, key: 'EUR', isPercent: false },
                        dr.rates.USD && { label: 'USD', value: dr.rates.USD.rate, key: 'USD', isPercent: false },
                        dr.rates.CNY && { label: 'CNY', value: dr.rates.CNY.rate, key: 'CNY', isPercent: false },
                      ].filter(Boolean) as Array<{ label: string; value: number; key: string; isPercent: boolean }>
                    : [];
                  const items: Array<{ label: string; value: number; key: string; isPercent: boolean }> = [
                    ...currencies,
                    ...(dr?.ruonia_rate != null ? [{ label: 'RUONIA', value: dr.ruonia_rate, key: 'RUONIA', isPercent: true }] : []),
                    ...(dr?.key_rate != null ? [{ label: 'Ключевая ставка', value: dr.key_rate, key: 'KEYRATE', isPercent: true }] : []),
                  ];
                  if (items.length === 0) {
                    return (
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          color: 'text.secondary',
                        }}
                      >
                        Данные не загружены
                      </Typography>
                    );
                  }
                  return items.map((item, index) => (
                    <React.Fragment key={item.key}>
                      <Typography
                        variant="caption"
                        sx={{
                          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          color: 'text.primary',
                        }}
                      >
                        {item.label}: <strong>{item.isPercent ? `${item.value.toFixed(2)}%` : item.value.toFixed(2)}</strong>
                      </Typography>
                      {index < items.length - 1 && (
                        <Box sx={{ width: '1px', height: '16px', bgcolor: 'divider' }} />
                      )}
                    </React.Fragment>
                  ));
                })()
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
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }, gap: 3 }}>
                      <HubCard
                        title="Кривая бескупонной доходности"
                        value={zerocuponLastDate || "—"}
                        subtitle="Анализ временной структуры процентных ставок на основе данных Мосбиржи"
                        icon={<TimelineIcon />}
                        color="#1976d2"
                        onClick={() => setForecastSubView('zerocupon')}
                      />
                      <HubCard
                        title="Среднесрочный прогноз Банка России"
                        value={forecastLastDate || "—"}
                        subtitle="Основные показатели денежно-кредитной политики и макроэкономические ожидания регулятора"
                        icon={<AssessmentIcon />}
                        color="#ff9800"
                        onClick={() => setForecastSubView('forecast')}
                      />
                      <HubCard
                        title="Ставка RUONIA"
                        value={dashboardRates?.ruonia_rate != null ? `${dashboardRates.ruonia_rate.toFixed(2)}%` : "—"}
                        subtitle="Информация о ставке RUONIA"
                        icon={<PercentIcon />}
                        color="#9c27b0"
                        onClick={() => setForecastSubView('ruonia')}
                      />
                      <HubCard
                        title="Ключевая ставка ЦБ"
                        value={dashboardRates?.key_rate != null ? `${dashboardRates.key_rate.toFixed(2)}%` : "—"}
                        subtitle="Информация о ключевой ставке Центрального Банка"
                        icon={<PercentIcon />}
                        color="#e91e63"
                        onClick={() => setForecastSubView('keyrate')}
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
                        <ForecastTable initialDates={availableForecastDates} />
                      </Box>
                    )}
                    
                    {forecastSubView === 'ruonia' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <RuoniaTable />
                      </Box>
                    )}
                    
                    {forecastSubView === 'keyrate' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <KeyRateTable />
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
              <>
                {comparisonSubView === null ? (
                  // Comparison Selection Screen
                  <Box
                    sx={{
                      width: '100%',
                      p: 3,
                    }}
                  >
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 3 }}>
                      <HubCard
                        title="Сравнение облигаций"
                        value="—"
                        subtitle="Сопоставление облигаций по ключевым метрикам"
                        icon={<AnalyticsIcon />}
                        color="#1976d2"
                        onClick={() => setComparisonSubView('comparison')}
                      />
                      <HubCard
                        title="Анализ кривой спредов"
                        value="—"
                        subtitle="Анализ спредов по эмитентам"
                        icon={<TimelineIcon />}
                        color="#ff9800"
                        onClick={() => setComparisonSubView('spread-analysis')}
                      />
                    </Box>
                  </Box>
                ) : (
                  // Comparison Content
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
                        onClick={() => setComparisonSubView(null)}
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
                        Назад к выбору разделов
                      </Button>
                    </Box>
                    
                    {/* Comparison Content */}
                    {comparisonSubView === 'comparison' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <ComparisonTable />
                      </Box>
                    )}
                    
                    {comparisonSubView === 'spread-analysis' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <SpreadAnalysis />
                      </Box>
                    )}
                  </Box>
                )}
              </>
            )}

            {currentTab === 5 && (
              <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                <BlogPage />
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
            setRefreshStatus({});
          }
        }}
        onConfirm={(tasks, forceRatings, forceCoupons, floatersProvider) => handleRefreshConfirm(tasks, forceRatings, forceCoupons, undefined, floatersProvider)}
        tasks={[
          { id: 'bonds', label: 'Обновить данные облигаций', checked: false },
          { id: 'zerocupon', label: 'Обновить данные кривой бескупонной доходности', checked: false },
          { id: 'ratings', label: 'Обновить рейтинги', checked: false },
          { id: 'emitents', label: 'Обновить эмитентов', checked: false },
          { id: 'coupons', label: 'Обновить купоны', checked: false },
          { id: 'currency', label: 'Обновить курсы валют', checked: false },
          { id: 'ruonia', label: 'Обновить данные ставки RUONIA', checked: false },
          { id: 'keyrate', label: 'Обновить ключевую ставку ЦБ', checked: false },
          { id: 'trading-history', label: 'Обновить историю торгов', checked: false },
          { id: 'forecast', label: 'Обновить среднесрочный прогноз Банка России', checked: false },
          { id: 'floaters', label: 'Обновить данные по флоатерам', checked: false },
        ]}
        isRefreshing={isRefreshing}
        refreshStatus={refreshStatus}
      />

      {/* Forecast file selection: after user chose "Обновить прогноз" and clicked Обновить */}
      <ForecastFileDialog
        open={isForecastFileDialogOpen}
        onClose={() => {
          setIsForecastFileDialogOpen(false);
          setPendingRefreshTasks([]);
        }}
        onConfirm={(file) => {
          setIsForecastFileDialogOpen(false);
          const tasks = pendingRefreshTasks;
          setPendingRefreshTasks([]);
          void handleRefreshConfirm(tasks, pendingForceUpdateRatings, pendingForceRefreshCoupons, file);
        }}
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
      <HelpDialog
        open={isHelpDialogOpen}
        onClose={() => setIsHelpDialogOpen(false)}
        section={getCurrentHelpSection()}
      />
    </Box>
  );
};

export default HomePage;
