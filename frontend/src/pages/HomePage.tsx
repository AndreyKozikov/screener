import React, { useState, useEffect } from 'react';
import { Container, Box, Typography, AppBar, Toolbar, Button, CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions, Alert, IconButton, Card, CardContent } from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon from '@mui/icons-material/Refresh';
import SettingsIcon from '@mui/icons-material/Settings';
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
import { ForecastHubCard } from '../components/forecast/ForecastHubCard';
import { RuoniaTable } from '../components/ruonia/RuoniaTable';
import { KeyRateTable } from '../components/keyrate/KeyRateTable';
import { Workbench } from '../components/portfolio/Workbench';
import { HubCard } from '../components/portfolio/HubCard';
import { ComparisonTable } from '../components/bonds/ComparisonTable';
import { SpreadAnalysis } from '../components/bonds/SpreadAnalysis';
import { AnalysisParamsDialog } from '../components/llm/AnalysisParamsDialog';
import { InflationExpectationsChart } from '../components/inflationExpectations/InflationExpectationsChart';
import { IpcPage } from '../components/ipc/IpcPage';
import { AnalysisResultDialog } from '../components/llm/AnalysisResultDialog';
import { LLMAnalysisModelDialog, type LLMModel } from '../components/llm/LLMAnalysisModelDialog';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { RefreshDataDialog } from '../components/common/RefreshDataDialog';
import { ForecastFileDialog } from '../components/common/ForecastFileDialog';
import { FeedbackDialog } from '../components/common/FeedbackDialog';
import { HelpDialog, type HelpSection } from '../components/common/HelpDialog';
import { SettingsDialog } from '../components/common/SettingsDialog';
import { HubCardIllustration, type HubCardIllustrationVariant } from '../components/common/HubCardIllustration';
import { BlogPage, type BlogMode } from './BlogPage';
import { refreshBondsData, refreshCouponsData } from '../api/bonds';
import { refreshFloatersData } from '../api/edisclosure';
import { refreshZerocuponData, fetchZerocuponData } from '../api/zerocupon';
import { refreshRatingsData } from '../api/rating';
import { refreshRuoniaData } from '../api/ruonia';
import { fetchForecastDates, uploadForecastPdf } from '../api/forecast';
import { refreshEmitentsData } from '../api/emitent';
import { refreshTradingHistory } from '../api/tradingHistory';
import { getDashboardRates, type MacroRatesResponse } from '../api/dashboard';
import { refreshCurrencyRates } from '../api/currency';
import { loadKeyRateData } from '../api/keyrate';
import { uploadAndParseIpcFile, parseLocalIpcFile, uploadIpcWeekly } from '../api/ipc';
import { uploadAndParseInflationExpectationsFile } from '../api/inflationExpectations';
import { uploadAndParseInflationFile } from '../api/inflation';
import { useUiStore } from '../stores/uiStore';
import { useBondsStore } from '../stores/bondsStore';
import { useComparisonStore } from '../stores/comparisonStore';
import { useSettingsStore } from '../stores/settingsStore';
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
  const settings = useSettingsStore((state) => state.settings);
  const [viewMode, setViewMode] = useState<ViewMode>('HUB');
  const [currentTab, setCurrentTab] = useState(0);
  const [blogMode, setBlogMode] = useState<BlogMode>('list');
  const [forecastSubView, setForecastSubView] = useState<'zerocupon' | 'forecast' | 'ruonia' | 'keyrate' | 'inflation-expectations' | 'ipc' | null>(null);
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
  const [pendingIpcFile, setPendingIpcFile] = useState<File | null>(null);
  const [pendingInflationExpectationsFile, setPendingInflationExpectationsFile] = useState<File | null>(null);
  const [pendingInflationFile, setPendingInflationFile] = useState<File | null>(null);
  
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
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  
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
    ipcFile?: File | null,
    inflationExpectationsFile?: File | null,
    inflationFile?: File | null,
  ) => {
    if (selectedTasks.length === 0) {
      return;
    }

    // If forecast is selected but no file yet — open file selection dialog first
    if (selectedTasks.includes('forecast') && forecastFile === undefined) {
      setPendingRefreshTasks(selectedTasks);
      setPendingForceUpdateRatings(forceUpdateRatings ?? false);
      setPendingForceRefreshCoupons(forceRefreshCoupons ?? false);
      setPendingIpcFile(ipcFile ?? null);
      setPendingInflationExpectationsFile(inflationExpectationsFile ?? null);
      setPendingInflationFile(inflationFile ?? null);
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
    const ipcFileRef = ipcFile ?? null;
    const inflationExpectationsFileRef = inflationExpectationsFile ?? null;
    const inflationFileRef = inflationFile ?? null;

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
          await uploadForecastPdf(forecastFileRef);
        }
      },
      floaters: async () => {
        await refreshFloatersData(floatersProvider ?? 'gemini');
      },
      ipc: async () => {
        if (ipcFileRef) {
          await uploadAndParseIpcFile(ipcFileRef);
        } else {
          await parseLocalIpcFile();
        }
      },
      'ipc-weekly': async () => {
        await uploadIpcWeekly();
      },
      'inflation-expectations': async () => {
        if (!inflationExpectationsFileRef) {
          throw new Error('Не выбран файл для обновления инфляционных ожиданий');
        }
        await uploadAndParseInflationExpectationsFile(inflationExpectationsFileRef);
      },
      inflation: async () => {
        if (!inflationFileRef) {
          throw new Error('Не выбран файл для обновления данных по инфляции');
        }
        await uploadAndParseInflationFile(inflationFileRef);
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
          settings.llmGptModel,
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
          settings.llmQwenModel,
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
          settings.llmGrokModel,
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
    if (tabIndex !== 5) {
      setBlogMode('list');
    }
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
    setBlogMode('list');
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
  const hubCards: Array<{
    title: string;
    description: string;
    icon: React.ReactNode;
    color: string;
    illustration: HubCardIllustrationVariant;
    onClick: () => void;
  }> = [
    {
      title: 'Рынок облигаций',
      description: 'Поиск и фильтрация активов',
      icon: <ShowChartIcon sx={{ fontSize: 32 }} />,
      color: '#1976d2',
      illustration: 'market',
      onClick: () => handleHubCardClick(0),
    },
    {
      title: 'Мой портфель',
      description: 'Управление инвестициями',
      icon: <AccountBalanceWalletIcon sx={{ fontSize: 32 }} />,
      color: '#4caf50',
      illustration: 'portfolio',
      onClick: () => handleHubCardClick(3),
    },
    {
      title: 'Прогнозы',
      description: 'Анализ и прогнозирование',
      icon: <TrendingUpIcon sx={{ fontSize: 32 }} />,
      color: '#ff9800',
      illustration: 'forecast',
      onClick: () => handleHubCardClick(2),
    },
    {
      title: 'Сравнение',
      description: 'Сопоставление облигаций',
      icon: <CompareArrowsIcon sx={{ fontSize: 32 }} />,
      color: '#9c27b0',
      illustration: 'comparison',
      onClick: () => handleHubCardClick(4),
    },
    {
      title: 'Блог',
      description: 'Статьи и интерактивный гид по облигациям',
      icon: <ArticleIcon sx={{ fontSize: 32 }} />,
      color: '#00acc1',
      illustration: 'blog',
      onClick: () => handleHubCardClick(5),
    },
  ];

  const marketMetrics = [
    { key: 'EUR', label: 'EUR', flag: '🇪🇺', value: dashboardRates?.rates.EUR?.rate, percent: false },
    { key: 'USD', label: 'USD', flag: '🇺🇸', value: dashboardRates?.rates.USD?.rate, percent: false },
    { key: 'CNY', label: 'CNY', flag: '🇨🇳', value: dashboardRates?.rates.CNY?.rate, percent: false },
    { key: 'RUONIA', label: 'RUONIA', flag: '%', value: dashboardRates?.ruonia_rate, percent: true },
    { key: 'KEYRATE', label: 'Ключевая ставка', flag: '%', value: dashboardRates?.key_rate, percent: true },
  ];

  const isForecastOverview = viewMode === 'TABLE' && currentTab === 2 && forecastSubView === null;
  const isBlogSection = viewMode === 'TABLE' && currentTab === 5;
  const isBlogDetail = isBlogSection && blogMode !== 'list';
  const usesGlassSurface = viewMode === 'HUB' || isForecastOverview || isBlogSection;

  return (
    <Box sx={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
      bgcolor: usesGlassSurface ? '#EAF3FF' : '#F4F7FD',
      backgroundImage: usesGlassSurface ? 'linear-gradient(180deg, rgba(236,244,255,0.08), rgba(236,244,255,0.18)), url("/images/bond-glass-background.png")' : 'none',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundAttachment: 'fixed',
    }}>
      {/* Compact App Bar */}
      <AppBar 
        position="sticky"
        elevation={0}
        sx={{
          top: 0,
          zIndex: (theme) => theme.zIndex.appBar,
          bgcolor: usesGlassSurface ? 'rgba(255,255,255,0.48)' : '#FFFFFF',
          color: '#10264A',
          borderBottom: '1px solid rgba(255,255,255,0.72)',
          backdropFilter: 'blur(20px)',
        }}
      >
        <Toolbar sx={{ minHeight: { xs: '52px !important', md: '62px !important' }, px: { xs: 1, md: 3.5 }, py: { xs: viewMode === 'TABLE' ? 0.5 : 0, md: 0 } }}>
          <Box sx={{
            display: 'grid',
            gridTemplateColumns: { xs: 'minmax(0, 1fr) auto', md: 'auto minmax(0, 1fr) auto' },
            alignItems: 'center',
            columnGap: { xs: 0.5, md: 1.5 },
            rowGap: { xs: 0.4, md: 0 },
            width: '100%',
            maxWidth: 1660,
            mx: 'auto',
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.75, sm: 1.5 }, gridColumn: '1 / 2', gridRow: '1 / 2', minWidth: 0 }}>
              <AccountBalanceIcon sx={{ fontSize: { xs: 22, sm: 27 }, color: '#17345B' }} />
              <Typography 
                variant="body1" 
                component="h1" 
                fontWeight={600}
                sx={{
                  fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  letterSpacing: '-0.01em',
                  fontSize: { xs: '0.75rem', sm: '1rem' },
                }}
              >
                Центр управления
              </Typography>
            </Box>
            {viewMode === 'TABLE' && (
              <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: { xs: 'flex-start', md: 'center' },
                gap: { xs: 0.5, sm: 1, md: 1.5 },
                gridColumn: { xs: '1 / -1', md: '2 / 3' },
                gridRow: { xs: '2 / 3', md: '1 / 2' },
                minWidth: 0,
                flexWrap: 'wrap',
              }}>
                <Button
                  startIcon={<ArrowBackIcon />}
                  onClick={handleBackToHub}
                  size="small"
                  sx={{
                    minWidth: 0,
                    px: { xs: 0.75, sm: 1 },
                    color: '#3d5d88',
                    textTransform: 'none',
                    whiteSpace: 'nowrap',
                    fontSize: { xs: '0.67rem', sm: '0.76rem' },
                    '& .MuiButton-startIcon': { mr: 0.5 },
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.58)' },
                  }}
                >
                  Назад в центр управления
                </Button>
                {isBlogDetail && (
                  <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={() => setBlogMode('list')}
                    size="small"
                    sx={{
                      minWidth: 0,
                      px: { xs: 0.75, sm: 1 },
                      color: '#3d5d88',
                      textTransform: 'none',
                      whiteSpace: 'nowrap',
                      fontSize: { xs: '0.67rem', sm: '0.76rem' },
                      '& .MuiButton-startIcon': { mr: 0.5 },
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.58)' },
                    }}
                  >
                    Назад к блогу
                  </Button>
                )}
              </Box>
            )}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: { xs: 0.25, sm: 0.75 }, gridColumn: { xs: '2 / 3', md: '3 / 4' }, gridRow: '1 / 2' }}>
              <IconButton
                size="small"
                aria-label="Настройки"
                onClick={() => setIsSettingsOpen(true)}
                sx={{ 
                  color: '#29476F', bgcolor: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.72)', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
                }}
              >
                <SettingsIcon sx={{ fontSize: 18 }} />
              </IconButton>
              <IconButton
                size="small"
                aria-label="Обновить данные"
                onClick={handleRefreshDataClick}
                disabled={isRefreshing}
                sx={{ 
                  color: '#29476F', bgcolor: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.72)', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
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
                aria-label="Анализ с помощью языковой модели"
                onClick={handleLLMAnalysisClick}
                disabled={isAnalyzing}
                sx={{ 
                  color: '#29476F', bgcolor: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.72)', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
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
                aria-label="Обратная связь"
                onClick={handleFeedbackClick}
                sx={{ 
                  color: '#29476F', bgcolor: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.72)', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
                }}
              >
                <FeedbackIcon sx={{ fontSize: 18 }} />
              </IconButton>
              <IconButton
                size="small"
                aria-label="Помощь"
                onClick={handleHelpClick}
                sx={{ 
                  color: '#29476F', bgcolor: 'rgba(255,255,255,0.42)', border: '1px solid rgba(255,255,255,0.72)', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.72)' },
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
        bgcolor: usesGlassSurface ? 'transparent' : '#F4F7FD',
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%', 
        ...(viewMode === 'TABLE'
          ? isBlogSection
            ? { minHeight: 'calc(100dvh - 62px)' }
            : { height: 'calc(100vh - 62px)' }
          : {})
      }}>
        {viewMode === 'HUB' ? (
          <>
            <Box
              component="section"
              aria-label="Добро пожаловать в BondsScreener"
              sx={{
                minHeight: { xs: 0, sm: 'clamp(150px, 30vh, 285px)' },
                display: 'flex',
                alignItems: 'center',
                color: '#10264A',
              }}
            >
              <Box sx={{
                width: '100%',
                maxWidth: 1660,
                mx: 'auto',
                px: { xs: 2, md: 3.5, xl: 4.5 },
                py: { xs: 2.5, sm: 1.5, md: 2.5 },
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: 'minmax(0, 1fr) minmax(310px, 0.95fr)' },
                alignItems: 'center',
                gap: { xs: 2, sm: 2, md: 4 },
              }}>
                <Box>
                  <Typography
                    component="h2"
                    sx={{ fontSize: { xs: '1.9rem', md: '2.55rem' }, lineHeight: 1.06, letterSpacing: '-0.04em', fontWeight: 760, maxWidth: 620, color: '#10264A' }}
                  >
                    Добро пожаловать<br />в BondsScreener
                  </Typography>
                  <Typography sx={{ mt: 1.35, fontSize: { xs: '0.95rem', md: '1.05rem' }, lineHeight: 1.5, color: '#263F66', maxWidth: 650 }}>
                    Анализируйте рынок облигаций, управляйте портфелем и принимайте взвешенные инвестиционные решения.
                  </Typography>
                </Box>

                <Box
                  aria-label="Курсы валют и процентные ставки"
                  sx={{
                    position: 'relative',
                    width: '100%',
                    maxWidth: 700,
                    justifySelf: 'end',
                    px: { xs: 1, sm: 1.5 },
                    py: { xs: 1, sm: 1.25 },
                    display: 'grid',
                    gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(6, minmax(0, 1fr))' },
                    alignItems: 'center',
                    border: '1px solid rgba(255,255,255,0.76)',
                    borderRadius: '22px',
                    background: 'rgba(255,255,255,0.46)',
                    boxShadow: '0 14px 34px rgba(68, 104, 171, 0.12), inset 0 1px 0 rgba(255,255,255,0.8)',
                    backdropFilter: 'blur(22px) saturate(145%)',
                  }}
                >
                  {marketMetrics.map((metric, index) => (
                    <Box
                      key={metric.key}
                      sx={{
                        gridColumn: { xs: 'span 1', sm: index < 3 ? 'span 2' : 'span 3' },
                        minWidth: 0,
                        minHeight: 58,
                        px: { xs: 0.75, sm: 1.5 },
                        display: 'flex',
                        alignItems: 'center',
                        gap: { xs: 0.75, sm: 1 },
                        borderBottom: index < 3 ? '1px solid rgba(255,255,255,0.6)' : 'none',
                      }}
                    >
                      <Box
                        sx={{
                          flexShrink: 0,
                          display: 'grid',
                          placeItems: 'center',
                          width: { xs: 32, sm: 38 },
                          height: { xs: 32, sm: 38 },
                          border: '1px solid rgba(255,255,255,0.86)',
                          borderRadius: '50%',
                          bgcolor: 'rgba(255,255,255,0.55)',
                          boxShadow: '0 3px 10px rgba(63, 104, 174, 0.1)',
                          color: '#1769E8',
                          fontSize: metric.percent ? '1rem' : '1.35rem',
                          fontWeight: 700,
                        }}
                      >
                        {metric.flag}
                      </Box>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.69rem', lineHeight: 1.25, fontWeight: 750, color: '#1D355B', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{metric.label}</Typography>
                        <Typography sx={{ mt: 0.1, fontSize: '0.94rem', lineHeight: 1.2, fontWeight: 760, color: '#10264A', fontVariantNumeric: 'tabular-nums' }}>
                          {metric.value == null ? '—' : `${metric.value.toFixed(2)}${metric.percent ? '%' : ''}`}
                        </Typography>
                        <Typography sx={{ mt: 0.1, fontSize: '0.64rem', lineHeight: 1.2, color: '#587092' }}>
                          {isLoadingDashboardRates ? 'обновляем…' : metric.percent ? 'годовых' : 'руб. за 1 ед.'}
                        </Typography>
                      </Box>
                    </Box>
                  ))}
                  {isLoadingDashboardRates && (
                    <CircularProgress size={14} sx={{ position: 'absolute', right: 8, top: 6, color: '#1769E8' }} />
                  )}
                </Box>
              </Box>
            </Box>

            <Box
              component="section"
              aria-label="Основные разделы BondsScreener"
              sx={{
                flexGrow: 1,
                px: { xs: 1.5, md: 3.5, xl: 4.5 },
                pb: { xs: 2, md: 4 },
                position: 'relative',
              }}
            >
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 132px), 1fr))',
                  gap: { xs: 1.25, md: 1.75 },
                  width: '100%',
                  maxWidth: 1660,
                  mx: 'auto',
                }}
              >
                {hubCards.map((card) => (
                  <Card
                    key={card.title}
                    role="button"
                    tabIndex={0}
                    aria-label={`${card.title}. ${card.description}`}
                    onClick={card.onClick}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        card.onClick();
                      }
                    }}
                    sx={{
                      position: 'relative',
                      display: 'block',
                      minWidth: 0,
                      height: { xs: 'clamp(210px, 36vh, 250px)', md: 'clamp(260px, 37vh, 350px)' },
                      overflow: 'hidden',
                      borderRadius: { xs: '16px', md: '22px' },
                      border: '1px solid rgba(255,255,255,0.82)',
                      background: `linear-gradient(145deg, rgba(255,255,255,0.58), ${card.color}12)`,
                      backdropFilter: 'blur(18px) saturate(145%)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      boxShadow: '0 8px 24px rgba(73, 105, 160, 0.1), inset 0 1px 0 rgba(255,255,255,0.8)',
                      transition: 'transform 220ms ease, box-shadow 220ms ease, background 220ms ease',
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        width: 130,
                        height: 130,
                        right: -52,
                        bottom: -60,
                        borderRadius: '50%',
                        background: `radial-gradient(circle, ${card.color}22 0%, ${card.color}00 72%)`,
                        pointerEvents: 'none',
                      },
                      '&:hover, &:focus-visible': {
                        transform: 'translateY(-3px)',
                        background: `linear-gradient(145deg, rgba(255,255,255,0.72), ${card.color}18)`,
                        boxShadow: '0 14px 34px rgba(73, 105, 160, 0.17), inset 0 1px 0 rgba(255,255,255,0.95)',
                      },
                      '&:focus-visible': { outline: `3px solid ${card.color}55`, outlineOffset: 2 },
                      '&:hover .hub-card-arrow, &:focus-visible .hub-card-arrow': { transform: 'translateX(3px)' },
                    }}
                  >
                    <CardContent sx={{ position: 'relative', zIndex: 1, height: '100%', p: { xs: 1.5, md: 2.5 }, '&:last-child': { pb: { xs: 1.5, md: 2.5 } } }}>
                      <Box
                        className="hub-card-icon"
                        sx={{
                          display: 'grid',
                          placeItems: 'center',
                          width: { xs: 38, md: 52 },
                          height: { xs: 38, md: 52 },
                          borderRadius: { xs: '10px', md: '13px' },
                          background: `linear-gradient(145deg, ${card.color}, ${card.color}D9)`,
                          color: '#FFFFFF',
                          boxShadow: `0 6px 14px ${card.color}32`,
                        }}
                      >
                        {card.icon}
                      </Box>
                      <Typography component="h3" sx={{ mt: { xs: 1.2, md: 1.8 }, fontSize: { xs: '0.84rem', md: '1.15rem' }, lineHeight: 1.22, fontWeight: 750, letterSpacing: '-0.025em', color: '#10264A' }}>
                        {card.title}
                      </Typography>
                      <Typography sx={{ mt: 0.7, maxWidth: { xs: 'calc(100% - 20px)', md: 220 }, fontSize: { xs: '0.69rem', md: '0.91rem' }, lineHeight: 1.4, color: '#3E5577' }}>
                        {card.description}
                      </Typography>
                    </CardContent>
                    <Box
                      className="hub-card-illustration"
                      aria-hidden="true"
                      sx={{
                        position: 'absolute',
                        zIndex: 0,
                        left: { xs: 8, md: 12 },
                        right: { xs: 8, md: 12 },
                        bottom: { xs: 8, md: 10 },
                        height: { xs: 62, md: 145 },
                        opacity: 0.92,
                        pointerEvents: 'none',
                        '& svg': { display: 'block', width: '100%', height: '100%' },
                      }}
                    >
                      <HubCardIllustration variant={card.illustration} color={card.color} />
                    </Box>
                    <Box
                      className="hub-card-arrow"
                      sx={{
                        position: 'absolute',
                        zIndex: 2,
                        right: { xs: 10, md: 16 },
                        bottom: { xs: 10, md: 16 },
                        width: { xs: 30, md: 40 },
                        height: { xs: 30, md: 40 },
                        display: 'grid',
                        placeItems: 'center',
                        borderRadius: '50%',
                        border: '1px solid rgba(255,255,255,0.88)',
                        color: card.color,
                        bgcolor: 'rgba(255,255,255,0.52)',
                        boxShadow: '0 3px 10px rgba(66, 99, 155, 0.12)',
                        transition: 'transform 180ms ease',
                        fontSize: { xs: '1.2rem', md: '1.5rem' },
                        lineHeight: 1,
                      }}
                    >
                      →
                    </Box>
                  </Card>
                ))}
              </Box>
            </Box>
          </>
        ) : (
          <Container 
            maxWidth={false} 
            sx={{ 
              px: isForecastOverview || isBlogSection ? 0 : 2,
              py: isForecastOverview ? { xs: 3, md: 6 } : isBlogSection ? { xs: 2, md: 3 } : 3,
              flexGrow: 1, 
              display: 'flex', 
              flexDirection: 'column', 
              width: '100%',
              bgcolor: isForecastOverview || isBlogSection ? 'transparent' : 'grey.50',
            }}
          >
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
                      maxWidth: 1532,
                      mx: 'auto',
                      px: { xs: 2, sm: 3, xl: 1.5 },
                      py: { xs: 2, sm: 3 },
                    }}
                  >
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(3, minmax(0, 1fr))' }, gap: { xs: 2, md: 2.25 } }}>
                      <ForecastHubCard
                        title="Кривая бескупонной доходности"
                        value={zerocuponLastDate || "—"}
                        subtitle="Анализ временной структуры процентных ставок на основе данных Мосбиржи"
                        icon={<TimelineIcon />}
                        color="#1976d2"
                        onClick={() => setForecastSubView('zerocupon')}
                      />
                      <ForecastHubCard
                        title="Среднесрочный прогноз Банка России"
                        value={forecastLastDate || "—"}
                        subtitle="Основные показатели денежно-кредитной политики и макроэкономические ожидания регулятора"
                        icon={<AssessmentIcon />}
                        color="#ff9800"
                        onClick={() => setForecastSubView('forecast')}
                      />
                      <ForecastHubCard
                        title="Ставка RUONIA"
                        value={dashboardRates?.ruonia_rate != null ? `${dashboardRates.ruonia_rate.toFixed(2)}%` : "—"}
                        subtitle="Информация о ставке RUONIA"
                        icon={<PercentIcon />}
                        color="#9c27b0"
                        onClick={() => setForecastSubView('ruonia')}
                      />
                      <ForecastHubCard
                        title="Ключевая ставка ЦБ"
                        value={dashboardRates?.key_rate != null ? `${dashboardRates.key_rate.toFixed(2)}%` : "—"}
                        subtitle="Информация о ключевой ставке Центрального Банка"
                        icon={<PercentIcon />}
                        color="#e91e63"
                        onClick={() => setForecastSubView('keyrate')}
                      />
                      <ForecastHubCard
                        title="Инфляционные ожидания"
                        value="—"
                        subtitle="Анализ инфляционных ожиданий населения"
                        icon={<AnalyticsIcon />}
                        color="#3f51b5"
                        onClick={() => setForecastSubView('inflation-expectations')}
                      />
                      <ForecastHubCard
                        title="Индекс потребительских цен"
                        value="—"
                        subtitle="Историческая динамика месячной и недельной инфляции"
                        icon={<AnalyticsIcon />}
                        color="#00897b"
                        onClick={() => setForecastSubView('ipc')}
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
                    
                    {forecastSubView === 'inflation-expectations' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <InflationExpectationsChart />
                      </Box>
                    )}

                    {forecastSubView === 'ipc' && (
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <IpcPage />
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
                <BlogPage mode={blogMode} onModeChange={setBlogMode} />
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
        onConfirm={(tasks, forceRatings, forceCoupons, floatersProvider, ipcFile, inflationExpectationsFile, inflationFile) => handleRefreshConfirm(tasks, forceRatings, forceCoupons, undefined, floatersProvider, ipcFile, inflationExpectationsFile, inflationFile)}
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
          { id: 'ipc', label: 'Обновить индексы потребительских цен (ИПЦ Росстата)', checked: false },
          { id: 'ipc-weekly', label: 'Обновить еженедельный ИПЦ', checked: false },
          { id: 'inflation-expectations', label: 'Обновить инфляционные ожидания', checked: false },
          { id: 'inflation', label: 'Обновление данных по инфляции', checked: false },
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
          setPendingIpcFile(null);
          setPendingInflationExpectationsFile(null);
          setPendingInflationFile(null);
        }}
        onConfirm={(file) => {
          setIsForecastFileDialogOpen(false);
          const tasks = pendingRefreshTasks;
          const savedIpcFile = pendingIpcFile;
          const savedInflationExpectationsFile = pendingInflationExpectationsFile;
          const savedInflationFile = pendingInflationFile;
          setPendingRefreshTasks([]);
          setPendingIpcFile(null);
          setPendingInflationExpectationsFile(null);
          setPendingInflationFile(null);
          void handleRefreshConfirm(tasks, pendingForceUpdateRatings, pendingForceRefreshCoupons, file, undefined, savedIpcFile, savedInflationExpectationsFile, savedInflationFile);
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
      <SettingsDialog
        open={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
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
