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
import { BlogPage } from './BlogPage';
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

const HubVisual: React.FC<{ index: number; color: string }> = ({ index, color }) => {
  const bars = [38, 58, 48, 76, 64, 94, 82, 118, 104, 142];

  return (
    <svg
      viewBox="0 0 360 190"
      preserveAspectRatio="xMidYMax meet"
      aria-hidden="true"
      focusable="false"
      style={{ display: 'block', width: '100%', height: '100%' }}
    >
      <defs>
        <linearGradient id={`hub-fill-${index}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.24" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      {index === 0 && (
        <>
          {bars.map((height, bar) => <rect key={bar} x={22 + bar * 31} y={178 - height} width="18" height={height} rx="7" fill={color} opacity={0.12 + bar * 0.015} />)}
          <path d="M12 151 C46 148 49 123 82 133 S126 106 155 116 S201 81 230 95 S278 57 348 18 L348 185 L12 185Z" fill={`url(#hub-fill-${index})`} />
          <path d="M12 151 C46 148 49 123 82 133 S126 106 155 116 S201 81 230 95 S278 57 348 18" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" />
        </>
      )}
      {index === 1 && (
        <>
          <circle cx="105" cy="108" r="66" fill="none" stroke={color} strokeOpacity="0.15" strokeWidth="28" />
          <circle cx="105" cy="108" r="66" fill="none" stroke={color} strokeWidth="28" strokeDasharray="255 160" transform="rotate(-90 105 108)" />
          {[0, 1, 2, 3].map((row) => (
            <g key={row} opacity={1 - row * 0.1}>
              <circle cx="226" cy={54 + row * 37} r="7" fill={color} />
              <rect x="246" y={47 + row * 37} width={96 - (row % 2) * 25} height="13" rx="7" fill={color} opacity="0.24" />
            </g>
          ))}
        </>
      )}
      {index === 2 && (
        <>
          {bars.slice(0, 9).map((height, bar) => <rect key={bar} x={26 + bar * 37} y={180 - height} width="23" height={height} rx="8" fill={color} opacity="0.12" />)}
          <path d="M14 154 C58 143 63 112 100 116 S150 121 181 88 S236 91 266 61 S314 40 349 10" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" />
          <circle cx="349" cy="10" r="6" fill={color} />
        </>
      )}
      {index === 3 && (
        <>
          <path d="M5 120 C45 120 55 72 96 81 S151 128 194 78 S248 50 279 68 S325 67 357 18 L357 185 L5 185Z" fill={`url(#hub-fill-${index})`} />
          <path d="M5 120 C45 120 55 72 96 81 S151 128 194 78 S248 50 279 68 S325 67 357 18" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" />
          <path d="M5 148 C47 148 65 121 106 133 S152 159 197 122 S249 106 286 119 S331 100 357 86" fill="none" stroke={color} strokeWidth="3" strokeOpacity="0.32" strokeDasharray="8 7" />
        </>
      )}
      {index === 4 && (
        <>
          <rect x="24" y="34" width="142" height="96" rx="12" fill={color} opacity="0.16" />
          <path d="M43 112 76 72 99 94 122 61 153 112Z" fill={color} opacity="0.45" />
          {[0, 1, 2].map((row) => <g key={row}><rect x="194" y={42 + row * 35} width={140 - row * 16} height="12" rx="6" fill={color} opacity="0.22" /><rect x="24" y={147 + row * 16} width={142 + row * 15} height="9" rx="5" fill={color} opacity="0.16" /></g>)}
        </>
      )}
    </svg>
  );
};

export const HomePage: React.FC = () => {
  const triggerDataRefresh = useUiStore((state) => state.triggerDataRefresh);
  const setError = useBondsStore((state) => state.setError);
  const comparisonBonds = useComparisonStore((state) => state.comparisonBonds);
  const settings = useSettingsStore((state) => state.settings);
  const [viewMode, setViewMode] = useState<ViewMode>('HUB');
  const [currentTab, setCurrentTab] = useState(0);
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
      title: 'Рынок облигаций',
      description: 'Поиск и фильтрация активов',
      icon: <ShowChartIcon sx={{ fontSize: 32 }} />,
      color: '#1976d2',
      onClick: () => handleHubCardClick(0),
    },
    {
      title: 'Мой Портфель',
      description: 'Управление инвестициями',
      icon: <AccountBalanceWalletIcon sx={{ fontSize: 32 }} />,
      color: '#4caf50',
      onClick: () => handleHubCardClick(3),
    },
    {
      title: 'Прогнозы',
      description: 'Анализ и прогнозирование',
      icon: <TrendingUpIcon sx={{ fontSize: 32 }} />,
      color: '#ff9800',
      onClick: () => handleHubCardClick(2),
    },
    {
      title: 'Сравнение',
      description: 'Сопоставление облигаций',
      icon: <CompareArrowsIcon sx={{ fontSize: 32 }} />,
      color: '#9c27b0',
      onClick: () => handleHubCardClick(4),
    },
    {
      title: 'Блог',
      description: 'Статьи и интерактивный гид по облигациям',
      icon: <ArticleIcon sx={{ fontSize: 32 }} />,
      color: '#00acc1',
      onClick: () => handleHubCardClick(5),
    },
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: '#F4F7FD' }}>
      {/* Compact App Bar */}
      <AppBar 
        position="static" 
        elevation={0}
        sx={{ bgcolor: '#FFFFFF', color: '#17345B', borderBottom: '1px solid #E7EDF7' }}
      >
        <Toolbar sx={{ minHeight: '68px !important', px: { xs: 1, md: 3.5 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', maxWidth: 1660, mx: 'auto', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.75, sm: 1.5 } }}>
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
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.25, sm: 0.75 } }}>
              <IconButton
                size="small"
                aria-label="Настройки"
                onClick={() => setIsSettingsOpen(true)}
                sx={{ 
                  color: '#29476F', bgcolor: '#F2F5FA', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: '#E7EEF8' },
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
                  color: '#29476F', bgcolor: '#F2F5FA', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: '#E7EEF8' },
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
                  color: '#29476F', bgcolor: '#F2F5FA', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: '#E7EEF8' },
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
                  color: '#29476F', bgcolor: '#F2F5FA', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: '#E7EEF8' },
                }}
              >
                <FeedbackIcon sx={{ fontSize: 18 }} />
              </IconButton>
              <IconButton
                size="small"
                aria-label="Помощь"
                onClick={handleHelpClick}
                sx={{ 
                  color: '#29476F', bgcolor: '#F2F5FA', width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 },
                  '&:hover': { bgcolor: '#E7EEF8' },
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
        bgcolor: '#F4F7FD', 
        display: 'flex', 
        flexDirection: 'column', 
        width: '100%', 
        ...(viewMode === 'TABLE' ? { height: 'calc(100vh - 68px)' } : {}) 
      }}>
        {viewMode === 'HUB' ? (
          <>
            <Box
              component="section"
              aria-label="Добро пожаловать в BondsScreener"
              sx={{
                minHeight: { xs: 320, md: 286 },
                display: 'flex',
                alignItems: 'center',
                color: '#FFFFFF',
                backgroundColor: '#123967',
                backgroundImage: 'linear-gradient(90deg, rgba(12, 43, 82, 0.94) 0%, rgba(16, 55, 102, 0.77) 35%, rgba(18, 55, 99, 0.12) 100%), url("/images/bond-market-hero.png")',
                backgroundSize: 'cover',
                backgroundPosition: 'center 48%',
              }}
            >
              <Box sx={{ width: '100%', maxWidth: 1660, mx: 'auto', px: { xs: 2.5, md: 5, xl: 6 }, py: { xs: 4, md: 4.5 } }}>
                <Typography
                  component="h2"
                  sx={{ fontSize: { xs: '2.2rem', md: '2.65rem' }, lineHeight: 1.08, letterSpacing: '-0.035em', fontWeight: 750, maxWidth: 620, textShadow: '0 2px 12px rgba(7, 24, 47, 0.18)' }}
                >
                  Добро пожаловать<br />в BondsScreener
                </Typography>
                <Typography sx={{ mt: 1.5, fontSize: { xs: '1rem', md: '1.15rem' }, lineHeight: 1.5, color: 'rgba(255,255,255,0.92)', maxWidth: 620 }}>
                  Анализируйте рынок облигаций, управляйте портфелем и принимайте взвешенные инвестиционные решения.
                </Typography>
              </Box>
            </Box>

            <Box
              component="section"
              aria-label="Основные разделы BondsScreener"
              sx={{
                flexGrow: 1,
                px: { xs: 2, md: 3.5, xl: 4.5 },
                pb: { xs: 3, md: 4 },
                mt: '-1px',
                borderRadius: '30px 30px 0 0',
                bgcolor: '#F4F7FD',
                position: 'relative',
              }}
            >
              {(() => {
                const metrics = [
                  { key: 'EUR', label: 'EUR', flag: '🇪🇺', value: dashboardRates?.rates.EUR?.rate, percent: false },
                  { key: 'USD', label: 'USD', flag: '🇺🇸', value: dashboardRates?.rates.USD?.rate, percent: false },
                  { key: 'CNY', label: 'CNY', flag: '🇨🇳', value: dashboardRates?.rates.CNY?.rate, percent: false },
                  { key: 'RUONIA', label: 'RUONIA', flag: '↗', value: dashboardRates?.ruonia_rate, percent: true },
                  { key: 'KEYRATE', label: 'Ключевая ставка', flag: '%', value: dashboardRates?.key_rate, percent: true },
                ];

                return (
                  <Box
                    sx={{
                      position: 'relative',
                      zIndex: 1,
                      maxWidth: 1070,
                      minHeight: 100,
                      mx: 'auto',
                      mt: { xs: -4, md: -6 },
                      mb: { xs: 3, md: 3.5 },
                      px: { xs: 1.5, sm: 2.5 },
                      py: 1.5,
                      display: 'grid',
                      gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))', md: 'repeat(5, minmax(0, 1fr))' },
                      alignItems: 'center',
                      border: '1px solid rgba(208, 221, 243, 0.9)',
                      borderRadius: '26px',
                      background: 'rgba(255,255,255,0.94)',
                      boxShadow: '0 14px 36px rgba(30, 69, 127, 0.12)',
                      backdropFilter: 'blur(16px)',
                    }}
                  >
                    {metrics.map((metric, index) => (
                      <Box
                        key={metric.key}
                        sx={{
                          minWidth: 0,
                          minHeight: 62,
                          px: { xs: 1, sm: 1.5 },
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1.25,
                          borderRight: { xs: 'none', md: index < metrics.length - 1 ? '1px solid #E7EDF7' : 'none' },
                          borderBottom: { xs: index < 4 ? '1px solid #EDF1F8' : 'none', sm: 'none' },
                        }}
                      >
                        <Box
                          sx={{
                            flexShrink: 0,
                            display: 'grid',
                            placeItems: 'center',
                            width: 40,
                            height: 40,
                            borderRadius: '50%',
                            bgcolor: metric.percent ? '#E8F1FF' : '#F2F6FD',
                            color: '#1769E8',
                            fontSize: metric.percent ? '1.05rem' : '1.45rem',
                            fontWeight: 700,
                          }}
                        >
                          {metric.flag}
                        </Box>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontSize: '0.73rem', lineHeight: 1.3, fontWeight: 700, color: '#243650', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{metric.label}</Typography>
                          <Typography sx={{ mt: 0.15, fontSize: '1.08rem', lineHeight: 1.25, fontWeight: 750, color: '#111D32', fontVariantNumeric: 'tabular-nums' }}>
                            {metric.value == null ? '—' : `${metric.value.toFixed(2)}${metric.percent ? '%' : ''}`}
                          </Typography>
                          <Typography sx={{ mt: 0.15, fontSize: '0.66rem', lineHeight: 1.2, color: '#71809A' }}>
                            {isLoadingDashboardRates ? 'обновляем…' : formatDateForDisplay(dashboardRates?.source_date ?? null) ?? 'по данным рынка'}
                          </Typography>
                        </Box>
                      </Box>
                    ))}
                    {isLoadingDashboardRates && (
                      <CircularProgress size={15} sx={{ position: 'absolute', right: 12, top: 8, color: '#1769E8' }} />
                    )}
                  </Box>
                );
              })()}

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(3, minmax(0, 1fr))', xl: 'repeat(5, minmax(0, 1fr))' },
                  gap: { xs: 2, md: 2.25 },
                  width: '100%',
                  maxWidth: 1660,
                  mx: 'auto',
                }}
              >
                {hubCards.map((card, index) => (
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
                      height: { xs: 340, md: 375, xl: 'min(414px, calc(100vh - 470px))' },
                      minHeight: { xl: 380 },
                      overflow: 'hidden',
                      borderRadius: '23px',
                      border: '1px solid',
                      borderColor: `${card.color}26`,
                      background: `linear-gradient(150deg, #FFFFFF 0%, ${card.color}0D 100%)`,
                      cursor: 'pointer',
                      textAlign: 'left',
                      boxShadow: '0 5px 20px rgba(37, 67, 112, 0.035)',
                      transition: 'transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease',
                      '&:hover, &:focus-visible': {
                        transform: 'translateY(-5px)',
                        borderColor: `${card.color}65`,
                        boxShadow: '0 16px 34px rgba(37, 67, 112, 0.12)',
                        outline: 'none',
                      },
                      '&:hover .hub-card-arrow, &:focus-visible .hub-card-arrow': { transform: 'translateX(3px)' },
                    }}
                  >
                    <CardContent sx={{ position: 'relative', zIndex: 1, height: '100%', p: { xs: 2.5, md: 3 }, '&:last-child': { pb: 3 } }}>
                      <Box
                        className="hub-card-icon"
                        sx={{
                          display: 'grid',
                          placeItems: 'center',
                          width: 58,
                          height: 58,
                          borderRadius: '15px',
                          bgcolor: card.color,
                          color: '#FFFFFF',
                          boxShadow: `0 7px 16px ${card.color}35`,
                        }}
                      >
                        {card.icon}
                      </Box>
                      <Typography component="h3" sx={{ mt: 2.35, fontSize: { xs: '1.25rem', md: '1.42rem' }, lineHeight: 1.2, fontWeight: 750, letterSpacing: '-0.025em', color: '#101D35' }}>
                        {card.title}
                      </Typography>
                      <Typography sx={{ mt: 1, maxWidth: 220, fontSize: '0.98rem', lineHeight: 1.45, color: '#526684' }}>
                        {card.description}
                      </Typography>
                    </CardContent>
                    <Box sx={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: '48%', opacity: 0.94, pointerEvents: 'none' }}>
                      <HubVisual index={index} color={card.color} />
                    </Box>
                    <Box
                      className="hub-card-arrow"
                      sx={{
                        position: 'absolute',
                        zIndex: 2,
                        right: 22,
                        bottom: 22,
                        width: 54,
                        height: 54,
                        display: 'grid',
                        placeItems: 'center',
                        borderRadius: '50%',
                        color: '#FFFFFF',
                        bgcolor: card.color,
                        boxShadow: `0 7px 16px ${card.color}35`,
                        transition: 'transform 180ms ease',
                        fontSize: '1.9rem',
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
                      <HubCard
                        title="Инфляционные ожидания"
                        value="—"
                        subtitle="Анализ инфляционных ожиданий населения"
                        icon={<AnalyticsIcon />}
                        color="#3f51b5"
                        onClick={() => setForecastSubView('inflation-expectations')}
                      />
                      <HubCard
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
