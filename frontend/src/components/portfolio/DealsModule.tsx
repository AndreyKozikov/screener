import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community';
import {
  Alert,
  Box,
  CircularProgress,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded';
import { fetchPortfolioDeals, type PortfolioDeal } from '../../api/portfolioDeals';
import { fetchImportedPortfolios, type ImportedPortfolioSummary } from '../../api/portfolioReportImport';
import { useSelectedReportPortfolioStore } from '../../stores/selectedReportPortfolioStore';

ModuleRegistry.registerModules([AllCommunityModule]);

const dealsGridTheme = themeQuartz.withParams({
  accentColor: '#1976d2',
  backgroundColor: '#ffffff',
  foregroundColor: '#26364a',
  borderColor: '#e4eaf2',
  chromeBackgroundColor: '#f7f9fc',
  headerBackgroundColor: '#f5f8fc',
  headerTextColor: '#42526b',
  headerFontSize: 13,
  headerFontWeight: 600,
  dataFontSize: 13,
  cellTextColor: '#26364a',
  cellHorizontalPadding: 10,
  rowHeight: 42,
  spacing: 8,
  wrapperBorder: { color: '#e4eaf2', width: 1 },
  wrapperBorderRadius: 8,
  headerRowBorder: { color: '#e4eaf2', width: 1 },
  columnBorder: false,
  rowBorder: { color: '#edf1f6', width: 1 },
  oddRowBackgroundColor: '#fcfdff',
  rowHoverColor: '#f2f7ff',
});

const localeText: Record<string, string> = {
  columnMenu: 'Меню столбца',
  filterMenuTab: 'Фильтр',
  generalMenuTab: 'Общие',
  columnsMenuTab: 'Столбцы',
  sortAscending: 'Сортировать по возрастанию',
  sortDescending: 'Сортировать по убыванию',
  sortUnSort: 'Сбросить сортировку',
  noRowsToShow: 'Нет сделок',
  loadingOoo: 'Загрузка…',
  page: 'Страница',
  more: 'ещё',
  to: '—',
  of: 'из',
  next: 'Следующая',
  last: 'Последняя',
  first: 'Первая',
  previous: 'Предыдущая',
};

const numberFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
const moneyFromMinor = (value: number | null | undefined) =>
  value == null ? '—' : numberFormat.format(value / 100);
const priceFromScaled = (value: number | null | undefined) =>
  value == null ? '—' : `${numberFormat.format(value / 10_000)}%`;
const dateRu = (value: string | null | undefined) => {
  if (!value) return '—';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : value;
};
const rawTooltip = (value: unknown) => (value == null ? '' : String(value));

const columnDefs: ColDef<PortfolioDeal>[] = [
  { field: 'id', headerName: 'ID сделки', width: 110, pinned: 'left' },
  { field: 'portfolio_id', headerName: 'ID портфеля', width: 120 },
  { field: 'security_id', headerName: 'ID бумаги', width: 110 },
  { field: 'security_name', headerName: 'Название облигации', minWidth: 250, flex: 1, pinned: 'left' },
  { field: 'security_code', headerName: 'SECID', width: 125 },
  { field: 'isin', headerName: 'ISIN', width: 145 },
  { field: 'trade_date', headerName: 'Дата сделки', width: 130, sort: 'desc', valueFormatter: ({ value }) => dateRu(value) },
  { field: 'settlement_date', headerName: 'Дата расчётов', width: 140, valueFormatter: ({ value }) => dateRu(value) },
  { field: 'trade_time', headerName: 'Время', width: 110 },
  { field: 'operation_type', headerName: 'Операция', width: 120, valueFormatter: ({ value }) => value === 'BUY' ? 'Покупка' : value === 'SELL' ? 'Продажа' : value ?? '—' },
  { field: 'quantity', headerName: 'Количество', width: 125, type: 'rightAligned' },
  { field: 'price_percent_scaled', headerName: 'Цена, % от номинала', width: 175, type: 'rightAligned', valueFormatter: ({ value }) => priceFromScaled(value) },
  { field: 'amount_ex_nkd_minor', headerName: 'Сумма без НКД', width: 155, type: 'rightAligned', valueFormatter: ({ value }) => moneyFromMinor(value) },
  { field: 'nkd_minor', headerName: 'НКД', width: 125, type: 'rightAligned', valueFormatter: ({ value }) => moneyFromMinor(value) },
  { field: 'broker_fee_minor', headerName: 'Комиссия брокера', width: 165, type: 'rightAligned', valueFormatter: ({ value }) => moneyFromMinor(value) },
  { field: 'exchange_fee_minor', headerName: 'Комиссия биржи', width: 155, type: 'rightAligned', valueFormatter: ({ value }) => moneyFromMinor(value) },
  { field: 'currency_code', headerName: 'Валюта сделки', width: 135 },
  { field: 'current_quantity', headerName: 'Количество сейчас', width: 155, type: 'rightAligned' },
  { field: 'security_currency_code', headerName: 'Валюта бумаги', width: 145 },
  { field: 'asset_type', headerName: 'Тип актива', width: 120 },
  { field: 'security_category', headerName: 'Категория бумаги', width: 170 },
  { field: 'issuer', headerName: 'Эмитент', width: 220 },
  { field: 'trade_number', headerName: 'Номер сделки', width: 150 },
  { field: 'status', headerName: 'Статус', width: 130 },
  { field: 'comment', headerName: 'Комментарий', width: 220 },
  { field: 'source_row_number', headerName: 'Строка отчёта', width: 135 },
  { field: 'raw_data_json', headerName: 'Исходные данные сделки', width: 260, tooltipValueGetter: ({ value }) => rawTooltip(value) },
  { field: 'security_raw_data_json', headerName: 'Исходные данные бумаги', width: 260, tooltipValueGetter: ({ value }) => rawTooltip(value) },
];

export const DealsModule: React.FC = () => {
  const portfolioId = useSelectedReportPortfolioStore((state) => state.portfolioId);
  const setPortfolioId = useSelectedReportPortfolioStore((state) => state.setPortfolioId);
  const [portfolios, setPortfolios] = useState<ImportedPortfolioSummary[]>([]);
  const [deals, setDeals] = useState<PortfolioDeal[]>([]);
  const [portfolioName, setPortfolioName] = useState('');
  const [search, setSearch] = useState('');
  const [loadingPortfolios, setLoadingPortfolios] = useState(true);
  const [loadingDeals, setLoadingDeals] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  const loadPortfolios = useCallback(async () => {
    setLoadingPortfolios(true);
    try {
      const items = await fetchImportedPortfolios();
      setPortfolios(items);
      const currentId = useSelectedReportPortfolioStore.getState().portfolioId;
      const selectedId = items.some((item) => item.portfolio_id === currentId)
        ? currentId
        : items[0]?.portfolio_id ?? null;
      setPortfolioId(selectedId);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить список портфелей.');
    } finally {
      setLoadingPortfolios(false);
    }
  }, [setPortfolioId]);

  useEffect(() => {
    void loadPortfolios();
  }, [loadPortfolios]);

  useEffect(() => {
    if (portfolioId == null) {
      setDeals([]);
      setPortfolioName('');
      setLoadingDeals(false);
      return;
    }
    let cancelled = false;
    setDeals([]);
    setPortfolioName('');
    setLoadingDeals(true);
    setError(null);
    fetchPortfolioDeals(portfolioId)
      .then((response) => {
        if (cancelled) return;
        setDeals(response.deals);
        setPortfolioName(response.portfolio_name);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить сделки портфеля.');
      })
      .finally(() => {
        if (!cancelled) setLoadingDeals(false);
      });
    return () => { cancelled = true; };
  }, [portfolioId, refreshNonce]);

  const filteredDeals = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('ru-RU');
    if (!query) return deals;
    return deals.filter((deal) => [deal.security_name, deal.isin, deal.security_code]
      .some((value) => value?.toLocaleLowerCase('ru-RU').includes(query)));
  }, [deals, search]);

  const defaultColDef = useMemo<ColDef<PortfolioDeal>>(() => ({
    sortable: true,
    resizable: true,
    filter: true,
    tooltipField: undefined,
    suppressHeaderMenuButton: true,
  }), []);

  const refresh = () => {
    setRefreshNonce((current) => current + 1);
    void loadPortfolios();
  };

  return (
    <Box sx={{ width: '100%', minWidth: 0, minHeight: 0, p: { xs: 1, sm: 2 }, background: 'linear-gradient(135deg, rgba(243,248,255,0.72) 0%, rgba(255,255,255,0.55) 56%, rgba(245,249,255,0.72) 100%)' }}>
      <Paper variant="outlined" sx={{ mb: { xs: 1.25, sm: 1.75 }, px: { xs: 1.25, sm: 2 }, py: { xs: 1.25, sm: 1.5 }, borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.88), rgba(246,250,255,0.78))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
        <Box sx={{ display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' }, justifyContent: 'space-between', gap: 1.5, flexWrap: 'wrap' }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
              <ReceiptLongRoundedIcon sx={{ color: '#1769E8', fontSize: 21 }} />
              <Typography component="h1" sx={{ color: '#102b50', fontWeight: 750, fontSize: { xs: '1.05rem', sm: '1.35rem' } }}>Сделки</Typography>
            </Box>
            <Typography sx={{ mt: 0.35, color: '#607693', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>
              {portfolioName ? `Сделки по облигациям портфеля «${portfolioName}»` : 'Операции по облигациям, которые сейчас находятся в портфеле'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', width: { xs: '100%', sm: 'auto' } }}>
            <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 230 } }} disabled={loadingPortfolios || portfolios.length === 0}>
              <InputLabel id="deals-portfolio-select-label">Текущий портфель</InputLabel>
              <Select
                labelId="deals-portfolio-select-label"
                value={portfolioId ?? ''}
                label="Текущий портфель"
                onChange={(event) => setPortfolioId(Number(event.target.value))}
              >
                {portfolios.map((item) => <MenuItem key={item.portfolio_id} value={item.portfolio_id}>{item.portfolio_name}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField
              size="small"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Название, ISIN или SECID"
              aria-label="Поиск сделок по облигации, ISIN или SECID"
              sx={{ minWidth: { xs: '100%', sm: 260 }, '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,.88)' } }}
              InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon sx={{ color: '#71829D', fontSize: 20 }} /></InputAdornment> }}
            />
            <Tooltip title="Обновить сделки и список портфелей">
              <span>
                <IconButton onClick={refresh} disabled={loadingPortfolios || loadingDeals} aria-label="Обновить сделки" sx={{ border: '1px solid #d5e1f0', borderRadius: 2, color: '#1769E8', bgcolor: 'rgba(255,255,255,.88)' }}>
                  {loadingDeals || loadingPortfolios ? <CircularProgress size={19} /> : <RefreshRoundedIcon />}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 1.5, borderRadius: 2 }}>{error}</Alert>}
      {!loadingPortfolios && !error && portfolios.length === 0 && (
        <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 }, borderRadius: 2, textAlign: 'center', borderColor: '#dce8f8', bgcolor: 'rgba(255,255,255,.82)' }}>
          <Typography sx={{ color: '#16345e', fontWeight: 700 }}>Портфель из брокерского отчёта не выбран</Typography>
          <Typography sx={{ mt: 0.5, color: '#71839d', fontSize: '.85rem' }}>Сначала импортируйте отчёт в подразделе «Портфель облигаций».</Typography>
        </Paper>
      )}
      {portfolios.length > 0 && (
        <Paper variant="outlined" sx={{ minWidth: 0, overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.86), rgba(255,255,255,0.74))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
          <Box sx={{ px: { xs: 1.25, sm: 2 }, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, borderBottom: '1px solid #EAF0F7' }}>
            <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '.9rem' }}>История сделок</Typography>
            <Typography sx={{ color: '#71839d', fontSize: '.78rem' }}>{filteredDeals.length} из {deals.length}</Typography>
          </Box>
          {deals.length === 0 && !loadingDeals ? (
            <Box sx={{ py: 5, px: 2, textAlign: 'center' }}>
              <Typography sx={{ color: '#16345e', fontWeight: 650 }}>Для текущих облигаций сделки не найдены</Typography>
              <Typography sx={{ mt: 0.45, color: '#71839d', fontSize: '.82rem' }}>В таблицу попадают операции по бумагам, которые остаются в закрывающем снимке портфеля.</Typography>
            </Box>
          ) : filteredDeals.length === 0 && !loadingDeals ? (
            <Box sx={{ py: 5, px: 2, textAlign: 'center', color: '#71839d', fontSize: '.85rem' }}>По запросу «{search}» сделок не найдено.</Box>
          ) : (
            <Box sx={{ width: '100%', height: 'calc(100vh - 250px)', minHeight: 340, p: { xs: 0.5, sm: 1.25 } }}>
              <AgGridReact<PortfolioDeal>
                theme={dealsGridTheme}
                rowData={filteredDeals}
                columnDefs={columnDefs}
                defaultColDef={defaultColDef}
                localeText={localeText}
                loading={loadingDeals}
                animateRows
                pagination
                paginationPageSize={50}
                paginationPageSizeSelector={[25, 50, 100, 250]}
                suppressCellFocus
              />
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default DealsModule;
