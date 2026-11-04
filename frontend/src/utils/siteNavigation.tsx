import type { SiteNavigationItem } from '../components/common/SiteNavigationDrawer';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import ArticleIcon from '@mui/icons-material/Article';
import SmartToyIcon from '@mui/icons-material/SmartToy';

/**
 * Общий модуль навигации по разделам сайта.
 * Используется и главной страницей, и страницей диалога с ИИ-ассистентом,
 * чтобы боковая панель сохранялась и вела себя одинаково на всех страницах.
 */

export const HOME_PAGE_VIEW_STORAGE_KEY = 'bonds-screener:home-page-view';

export type SiteViewMode = 'HUB' | 'TABLE';
export type SiteBlogMode = 'list' | 'guide';
export type SiteForecastSubView =
  | 'macro-dashboard'
  | 'zerocupon'
  | 'forecast'
  | 'ruonia'
  | 'keyrate'
  | 'inflation-expectations'
  | 'ipc'
  | 'sustainable-inflation';
export type SiteComparisonSubView = 'comparison' | 'spread-analysis';
export type SitePortfolioModule = 'HUB' | 'PORTFOLIO' | 'CALENDAR' | 'ANALYTICS';

export type SavedHomePageView = {
  viewMode: SiteViewMode;
  currentTab: number;
  blogMode: SiteBlogMode;
  forecastSubView: SiteForecastSubView | null;
  comparisonSubView: SiteComparisonSubView | null;
  portfolioModule: SitePortfolioModule;
};

export const DEFAULT_HOME_PAGE_VIEW: SavedHomePageView = {
  viewMode: 'HUB',
  currentTab: 0,
  blogMode: 'list',
  forecastSubView: null,
  comparisonSubView: null,
  portfolioModule: 'HUB',
};

const FORECAST_SUB_VIEWS: SiteForecastSubView[] = [
  'macro-dashboard', 'zerocupon', 'forecast', 'ruonia', 'keyrate', 'inflation-expectations', 'ipc', 'sustainable-inflation',
];
const COMPARISON_SUB_VIEWS: SiteComparisonSubView[] = ['comparison', 'spread-analysis'];
const PORTFOLIO_MODULES: SitePortfolioModule[] = ['HUB', 'PORTFOLIO', 'CALENDAR', 'ANALYTICS'];

export const readSavedHomePageView = (): SavedHomePageView => {
  if (typeof window === 'undefined') return DEFAULT_HOME_PAGE_VIEW;

  try {
    const serializedView = window.sessionStorage.getItem(HOME_PAGE_VIEW_STORAGE_KEY);
    if (!serializedView) return DEFAULT_HOME_PAGE_VIEW;

    const savedView = JSON.parse(serializedView) as Partial<SavedHomePageView>;
    const currentTab = Number(savedView.currentTab);

    return {
      viewMode: savedView.viewMode === 'TABLE' ? 'TABLE' : 'HUB',
      currentTab: Number.isInteger(currentTab) && currentTab >= 0 && currentTab <= 5 ? currentTab : 0,
      // BlogPage keeps the selected article in memory, so restore the list after a reload.
      blogMode: savedView.blogMode === 'guide' ? 'guide' : 'list',
      forecastSubView: FORECAST_SUB_VIEWS.includes(savedView.forecastSubView as SiteForecastSubView)
        ? savedView.forecastSubView as SiteForecastSubView
        : null,
      comparisonSubView: COMPARISON_SUB_VIEWS.includes(savedView.comparisonSubView as SiteComparisonSubView)
        ? savedView.comparisonSubView as SiteComparisonSubView
        : null,
      portfolioModule: PORTFOLIO_MODULES.includes(savedView.portfolioModule as SitePortfolioModule)
        ? savedView.portfolioModule as SitePortfolioModule
        : DEFAULT_HOME_PAGE_VIEW.portfolioModule,
    };
  } catch {
    return DEFAULT_HOME_PAGE_VIEW;
  }
};

export const writeSavedHomePageView = (view: SavedHomePageView): void => {
  try {
    window.sessionStorage.setItem(HOME_PAGE_VIEW_STORAGE_KEY, JSON.stringify(view));
  } catch {
    // Keep the page usable when browser storage is unavailable.
  }
};

export const siteNavigationItems: SiteNavigationItem[] = [
  {
    id: 'home',
    label: 'Центр управления',
    icon: <HomeOutlinedIcon />,
  },
  {
    id: 'market',
    label: 'Рынок облигаций',
    icon: <ShowChartIcon />,
  },
  {
    id: 'forecasts',
    label: 'Прогнозы',
    icon: <TrendingUpIcon />,
    children: [
      { id: 'forecast:macro-dashboard', label: 'Макроэкономический обзор' },
      { id: 'forecast:zerocupon', label: 'Кривая бескупонной доходности' },
      { id: 'forecast:forecast', label: 'Среднесрочный прогноз Банка России' },
      { id: 'forecast:ruonia', label: 'Ставка RUONIA' },
      { id: 'forecast:keyrate', label: 'Ключевая ставка ЦБ' },
      { id: 'forecast:inflation-expectations', label: 'Инфляционные ожидания' },
      { id: 'forecast:ipc', label: 'Индекс потребительских цен' },
      { id: 'forecast:sustainable-inflation', label: 'Устойчивая инфляция' },
    ],
  },
  {
    id: 'portfolio',
    label: 'Мой портфель',
    icon: <AccountBalanceWalletIcon />,
    children: [
      { id: 'portfolio:holdings', label: 'Портфель облигаций' },
      { id: 'portfolio:calendar', label: 'Календарь выплат' },
      { id: 'portfolio:analytics', label: 'Аналитика портфеля' },
    ],
  },
  {
    id: 'comparison',
    label: 'Сравнение',
    icon: <CompareArrowsIcon />,
    children: [
      { id: 'comparison:comparison', label: 'Сравнение облигаций' },
      { id: 'comparison:spread-analysis', label: 'Анализ кривой спредов' },
    ],
  },
  {
    id: 'blog',
    label: 'Блог',
    icon: <ArticleIcon />,
    children: [
      { id: 'blog:guide', label: 'Гид по выбору облигаций' },
    ],
  },
  {
    id: 'chat',
    label: 'Чат с ИИ',
    icon: <SmartToyIcon />,
  },
];

/**
 * Преобразует id раздела боковой панели в полное описание вида главной страницы.
 * Используется главной страницей (применение состояния) и страницей диалога
 * (запись состояния в sessionStorage перед переходом на главную).
 */
export const resolveSiteNavigationTarget = (id: string): SavedHomePageView => {
  const tab = (currentTab: number, overrides: Partial<SavedHomePageView> = {}): SavedHomePageView => ({
    viewMode: 'TABLE',
    currentTab,
    blogMode: currentTab === 5 ? 'guide' : 'list',
    forecastSubView: null,
    comparisonSubView: null,
    portfolioModule: 'HUB',
    ...overrides,
  });

  switch (id) {
    case 'home':
      return DEFAULT_HOME_PAGE_VIEW;
    case 'market':
      return tab(0);
    case 'forecasts':
      return tab(2);
    case 'forecast:macro-dashboard':
      return tab(2, { forecastSubView: 'macro-dashboard' });
    case 'forecast:zerocupon':
      return tab(2, { forecastSubView: 'zerocupon' });
    case 'forecast:forecast':
      return tab(2, { forecastSubView: 'forecast' });
    case 'forecast:ruonia':
      return tab(2, { forecastSubView: 'ruonia' });
    case 'forecast:keyrate':
      return tab(2, { forecastSubView: 'keyrate' });
    case 'forecast:inflation-expectations':
      return tab(2, { forecastSubView: 'inflation-expectations' });
    case 'forecast:ipc':
      return tab(2, { forecastSubView: 'ipc' });
    case 'forecast:sustainable-inflation':
      return tab(2, { forecastSubView: 'sustainable-inflation' });
    case 'portfolio':
      return tab(3);
    case 'portfolio:holdings':
      return tab(3, { portfolioModule: 'PORTFOLIO' });
    case 'portfolio:calendar':
      return tab(3, { portfolioModule: 'CALENDAR' });
    case 'portfolio:analytics':
      return tab(3, { portfolioModule: 'ANALYTICS' });
    case 'comparison':
      return tab(4);
    case 'comparison:comparison':
      return tab(4, { comparisonSubView: 'comparison' });
    case 'comparison:spread-analysis':
      return tab(4, { comparisonSubView: 'spread-analysis' });
    case 'blog':
      return tab(5, { blogMode: 'list' });
    case 'blog:guide':
      return tab(5, { blogMode: 'guide' });
    default:
      return DEFAULT_HOME_PAGE_VIEW;
  }
};
