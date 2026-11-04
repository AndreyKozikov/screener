import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Card, CircularProgress, Paper, Typography, alpha } from '@mui/material';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import PercentRoundedIcon from '@mui/icons-material/PercentRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import PieChartOutlineRoundedIcon from '@mui/icons-material/PieChartOutlineRounded';
import LayersRoundedIcon from '@mui/icons-material/LayersRounded';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { fetchPortfolioValuation, type PortfolioValuation } from '../../api/portfolioValuation';

const COLORS = ['#1769E8', '#34A7F5', '#22B8B0', '#8C78F5', '#F2A94A', '#5284C7', '#44C7A3', '#A8B8D0'];
const todayLocal = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};
const money = (value?: string | null, currency = 'RUB') => value == null ? '—' : new Intl.NumberFormat('ru-RU', { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(value));
const percent = (value?: string | null) => value == null ? '—' : `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value))}%`;

type MetricProps = { title: string; value: string; subtitle: string; color: string; icon: React.ReactNode };
const MetricCard: React.FC<MetricProps> = ({ title, value, subtitle, color, icon }) => (
  <Card variant="outlined" sx={{ minWidth: 0, borderColor: '#d9e7fb', borderRadius: 2, borderLeft: `3px solid ${color}`, background: 'linear-gradient(145deg, rgba(255,255,255,0.82), rgba(242,247,255,0.76))', boxShadow: '0 2px 8px rgba(30, 81, 145, 0.06)' }}>
    <Box sx={{ p: { xs: 1.2, sm: 1.6 } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: '#365477', minHeight: 30 }}>
        <Box sx={{ display: 'grid', placeItems: 'center', color, '& svg': { fontSize: 19 } }}>{icon}</Box>
        <Typography sx={{ color: '#365477', fontSize: { xs: '.72rem', sm: '.78rem' }, lineHeight: 1.25, fontWeight: 600 }}>{title}</Typography>
      </Box>
      <Typography sx={{ mt: 0.7, color: '#122d51', fontSize: { xs: '1.2rem', sm: '1.45rem' }, fontWeight: 750, lineHeight: 1.05, fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>{value}</Typography>
      <Typography sx={{ mt: 0.65, color: '#607693', fontSize: { xs: '.66rem', sm: '.72rem' } }}>{subtitle}</Typography>
    </Box>
  </Card>
);

export const AnalyticsModule: React.FC = () => {
  const bonds = usePortfolioStore((state) => state.portfolioBonds);
  const [valuationDate, setValuationDate] = useState(todayLocal);
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!bonds.length) { setValuation(null); setError(null); return; }
    setLoading(true); setError(null);
    try { setValuation(await fetchPortfolioValuation(bonds, valuationDate)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Не удалось оценить портфель'); }
    finally { setLoading(false); }
  }, [bonds, valuationDate]);

  useEffect(() => { void refresh(); }, [refresh]);

  const allocation = useMemo(() => (valuation?.positions ?? []).map((position) => ({
    name: position.name || position.secid,
    secid: position.secid,
    value: Number(position.market_value),
    weight: Number(position.weight_percent),
  })).sort((a, b) => b.value - a.value), [valuation]);

  const topPosition = allocation[0];
  const currency = valuation?.currency || 'RUB';
  const maturityData = useMemo(() => {
    const buckets = new Map<string, number>();
    (valuation?.positions ?? []).forEach((position) => {
      if (!position.maturity_date) return;
      const year = position.maturity_date.slice(0, 4);
      buckets.set(year, (buckets.get(year) ?? 0) + Number(position.market_value));
    });
    return [...buckets.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([year, value]) => ({ year, value }));
  }, [valuation]);
  const yieldByMaturity = useMemo(() => (valuation?.positions ?? []).flatMap((position) => {
    if (!position.maturity_date || position.ytm_percent == null) return [];
    const end = new Date(`${position.maturity_date.slice(0, 10)}T00:00:00`);
    const start = new Date(`${valuationDate}T00:00:00`);
    const termYears = (end.getTime() - start.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
    if (!Number.isFinite(termYears) || termYears < 0) return [];
    return [{ secid: position.secid, name: position.name || position.secid, termYears, ytm: Number(position.ytm_percent) }];
  }), [valuation, valuationDate]);

  return (
    <Box sx={{ width: '100%', minWidth: 0, minHeight: 0, p: { xs: 1, sm: 2 }, background: 'linear-gradient(135deg, rgba(243,248,255,0.72) 0%, rgba(255,255,255,0.55) 56%, rgba(245,249,255,0.72) 100%)', borderRadius: 2 }}>
      <Paper variant="outlined" sx={{ mb: { xs: 1.25, sm: 1.75 }, px: { xs: 1.25, sm: 2 }, py: { xs: 1.25, sm: 1.5 }, borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.82), rgba(246,250,255,0.72))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
        <Box sx={{ display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' }, justifyContent: 'space-between', gap: 1.5, flexWrap: 'wrap' }}>
        <Box>
          <Typography component="h1" sx={{ color: '#102b50', fontWeight: 750, fontSize: { xs: '1.05rem', sm: '1.35rem' } }}>Аналитика портфеля</Typography>
          <Typography sx={{ mt: 0.35, color: '#607693', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>Структура и доходность портфеля облигаций</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'end', gap: 1 }}>
          <Box><Typography component="label" htmlFor="portfolio-valuation-date" sx={{ display: 'block', mb: .45, color: '#29476F', fontSize: '.75rem', fontWeight: 600 }}>Дата оценки</Typography><input id="portfolio-valuation-date" type="date" value={valuationDate} max={todayLocal()} onChange={(event) => setValuationDate(event.target.value)} style={{ height: 40, border: '1px solid #D5E1F0', borderRadius: 10, padding: '0 10px', color: '#10264A', background: 'rgba(255,255,255,.9)', font: 'inherit' }} /></Box>
          <Button onClick={() => void refresh()} disabled={loading || !bonds.length} startIcon={loading ? <CircularProgress size={17} color="inherit" /> : <RefreshRoundedIcon />} sx={{ height: 42, px: 2, borderRadius: 2.5, color: '#fff', textTransform: 'none', fontWeight: 650, whiteSpace: 'nowrap', background: 'linear-gradient(135deg, #258BFA, #0758F5)', boxShadow: '0 5px 14px rgba(23,105,232,.24)', '&:hover': { background: 'linear-gradient(135deg, #1879E8, #034BD8)' }, '&.Mui-disabled': { color: '#fff', bgcolor: '#9BBBEF' } }}>Обновить</Button>
        </Box>
      </Box>
      </Paper>

      <Box>
        {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 3 }}>{error}</Alert>}
        {!bonds.length ? <Card sx={{ p: 4, borderRadius: 5, textAlign: 'center', border: '1px solid #E2E8F0', boxShadow: 'none', bgcolor: alpha('#fff', .85) }}><Typography sx={{ fontWeight: 700, color: '#10264A', fontSize: '1.1rem' }}>Портфель пока пуст</Typography><Typography sx={{ mt: .75, color: '#647895' }}>Добавьте облигации в разделе «Портфель», чтобы рассчитать стоимость и доходность.</Typography></Card> : valuation && <>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2,minmax(0,1fr))', sm: 'repeat(4,minmax(0,1fr))' }, gap: { xs: 0.85, sm: 1.25 }, mb: { xs: 1.25, sm: 1.75 } }}>
            <MetricCard title="Рыночная стоимость" value={money(valuation.total_market_value, currency)} subtitle="С учётом НКД" color="#1769E8" icon={<AccountBalanceWalletOutlinedIcon />} />
            <MetricCard title="Средневзвешенная доходность" value={percent(valuation.weighted_ytm_percent)} subtitle="Годовых к погашению" color="#2788E8" icon={<PercentRoundedIcon />} />
            <MetricCard title="Истинная доходность (IRR)" value={percent(valuation.true_ytm_percent)} subtitle="Годовых по будущим выплатам" color="#16A58D" icon={<TrendingUpRoundedIcon />} />
            <MetricCard title="Количество позиций" value={String(valuation.positions.length)} subtitle="Позиции с ненулевым количеством" color="#5894E8" icon={<LayersRoundedIcon />} />
          </Box>

          <Paper variant="outlined" sx={{ minWidth: 0, overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.8), rgba(255,255,255,0.62))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
            <Box sx={{ px: { xs: 1.25, sm: 2 }, pt: 1.35, pb: 0.25, borderBottom: '1px solid #EAF0F7' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><PieChartOutlineRoundedIcon sx={{ color: '#1769E8', fontSize: 19 }} /><Typography component="h2" sx={{ color: '#16345e', fontWeight: 700, fontSize: '.9rem' }}>Структура портфеля</Typography></Box>
              <Typography sx={{ mt: .25, color: '#71839d', fontSize: '.72rem' }}>Распределение грязной рыночной стоимости по облигациям</Typography>
            </Box>
            {valuation.warnings.length > 0 && <Box sx={{ px: 2.5, pt: 2, display: 'grid', gap: 1 }}>{valuation.warnings.map((warning, index) => <Alert key={`${index}-${warning}`} severity="warning" sx={{ borderRadius: 2 }}>{warning}</Alert>)}</Box>}
            <Box sx={{ p: { xs: 1.5, md: 2.5 }, display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'minmax(260px, .9fr) minmax(260px, 1.1fr)' }, alignItems: 'center', gap: 2 }}>
              <Box sx={{ position: 'relative', height: { xs: 255, sm: 310 }, minWidth: 0 }}>
                <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={allocation} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="86%" paddingAngle={2} stroke="none">{allocation.map((entry, index) => <Cell key={entry.secid} fill={COLORS[index % COLORS.length]} />)}</Pie><ChartTooltip formatter={(value) => money(String(value), currency)} labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ''} /></PieChart></ResponsiveContainer>
                <Box sx={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}><Typography sx={{ color: '#10264A', fontWeight: 700, fontSize: '1.25rem' }}>{money(valuation.total_market_value, currency)}</Typography><Typography sx={{ color: '#71829D', fontSize: '.8rem' }}>Всего</Typography></Box>
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: 1, px: 1, pb: 1, color: '#71829D', fontSize: '.75rem', fontWeight: 600 }}><span>Облигация</span><span>Доля</span></Box>
                <Box sx={{ maxHeight: 300, overflow: 'auto' }}>{allocation.map((entry, index) => <Box key={entry.secid} sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', alignItems: 'center', gap: 1, px: 1, py: 1.15, borderTop: '1px solid #EDF2F8' }}><Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}><Box sx={{ width: 10, height: 10, flex: '0 0 auto', borderRadius: '50%', bgcolor: COLORS[index % COLORS.length] }} /><Box sx={{ minWidth: 0 }}><Typography noWrap sx={{ fontSize: '.85rem', color: '#10264A', fontWeight: 600 }}>{entry.name}</Typography><Typography sx={{ fontSize: '.72rem', color: '#71829D' }}>{entry.secid}</Typography></Box></Box><Typography sx={{ color: '#29476F', fontSize: '.82rem', fontWeight: 600 }}>{percent(entry.weight)}</Typography></Box>)}</Box>
                {topPosition && <Typography sx={{ mt: 1.5, px: 1, color: '#71829D', fontSize: '.78rem' }}>Крупнейшая позиция: <Box component="span" sx={{ color: '#29476F', fontWeight: 600 }}>{topPosition.name} · {percent(String(topPosition.weight))}</Box></Typography>}
              </Box>
            </Box>
          </Paper>

          <Box sx={{ mt: { xs: 1.25, sm: 1.75 }, display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(2,minmax(0,1fr))' }, gap: { xs: 1.25, sm: 1.75 } }}>
            <Paper variant="outlined" sx={{ minWidth: 0, overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.8), rgba(255,255,255,0.62))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
              <Box sx={{ px: { xs: 1.25, sm: 2 }, pt: 1.35, pb: 0.25 }}>
                <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '.9rem' }}>Погашения по годам</Typography>
                <Typography sx={{ mt: .25, color: '#71839d', fontSize: '.72rem' }}>Рыночная стоимость позиций по году погашения</Typography>
              </Box>
              {maturityData.length ? <Box sx={{ width: '100%', height: 250, px: 1, pt: 1 }}><ResponsiveContainer><BarChart data={maturityData} margin={{ top: 8, right: 12, bottom: 4, left: 8 }}><CartesianGrid stroke="#e9f0fa" vertical={false} /><XAxis dataKey="year" tick={{ fill: '#56708f', fontSize: 11 }} axisLine={{ stroke: '#d7e3f2' }} tickLine={false} /><YAxis tickFormatter={(value: number) => new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 0 }).format(value)} tick={{ fill: '#71839d', fontSize: 10 }} axisLine={false} tickLine={false} width={54} /><ChartTooltip formatter={(value) => money(String(value), currency)} labelFormatter={(label) => `Погашение: ${label}`} /><Bar dataKey="value" name="Рыночная стоимость" fill="#5BA9F4" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></Box> : <Typography sx={{ p: 3, color: '#71839d', fontSize: '.8rem' }}>Нет дат погашения для построения графика</Typography>}
            </Paper>

            <Paper variant="outlined" sx={{ minWidth: 0, overflow: 'hidden', borderRadius: 2, borderColor: '#dce8f8', background: 'linear-gradient(145deg, rgba(255,255,255,0.8), rgba(255,255,255,0.62))', boxShadow: '0 2px 7px rgba(30, 81, 145, 0.04)' }}>
              <Box sx={{ px: { xs: 1.25, sm: 2 }, pt: 1.35, pb: 0.25 }}>
                <Typography sx={{ color: '#16345e', fontWeight: 700, fontSize: '.9rem' }}>Доходность по сроку до погашения</Typography>
                <Typography sx={{ mt: .25, color: '#71839d', fontSize: '.72rem' }}>YTM отдельных позиций из оценки backend</Typography>
              </Box>
              {yieldByMaturity.length ? <Box sx={{ width: '100%', height: 250, px: 1, pt: 1 }}><ResponsiveContainer><ScatterChart margin={{ top: 8, right: 18, bottom: 8, left: 8 }}><CartesianGrid stroke="#e9f0fa" /><XAxis type="number" dataKey="termYears" name="Срок до погашения" unit=" лет" domain={[0, 'dataMax']} tick={{ fill: '#56708f', fontSize: 11 }} axisLine={{ stroke: '#d7e3f2' }} tickLine={false} /><YAxis type="number" dataKey="ytm" name="YTM" unit="%" tick={{ fill: '#71839d', fontSize: 10 }} axisLine={false} tickLine={false} width={48} /><ChartTooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value, name) => [name === 'YTM' ? `${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}%` : `${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} лет`, name]} labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ''} /><Scatter data={yieldByMaturity} fill="#3977c3" /></ScatterChart></ResponsiveContainer></Box> : <Typography sx={{ p: 3, color: '#71839d', fontSize: '.8rem' }}>Нет одновременно доступных YTM и даты погашения</Typography>}
            </Paper>
          </Box>
        </>}
      </Box>
    </Box>
  );
};
