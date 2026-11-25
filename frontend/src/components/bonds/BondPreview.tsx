import { BondIdentity } from './BondIdentity';
import { getEmitentBySecid, type EmitentInfo } from '../../api/emitent';
import { amortization, useCouponTerms } from './couponTerms';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Alert, Box, Button, Chip, Drawer, IconButton, Stack, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { fetchBondCoupons, fetchBondDetail } from '../../api/bonds';
import type { BondDetail, BondFieldValue } from '../../types/bond';
import { formatDate, formatNumber, formatPercent } from '../../utils/formatters';

function offerType(detail: BondDetail) {
  const { PUTOPTIONDATE, CALLOPTIONDATE, OFFERDATE } = detail.securities;
  const subtype = String(detail.bond_description?.bond_subtype ?? '');
  const types = [];
  if (PUTOPTIONDATE || /\bput\b|пут[- ]опцион/i.test(subtype)) types.push('PUT');
  if (CALLOPTIONDATE || /\bcall\b|колл?[- ]опцион/i.test(subtype)) types.push('CALL');
  if (types.length) return types.join(' / ');
  return OFFERDATE ? 'Тип не указан' : '—';
}

function display(value: BondFieldValue | undefined) {
  return value == null || value === '' ? 'Нет данных' : String(value);
}

function percentage(value: BondFieldValue | undefined) {
  return typeof value === 'number' ? formatPercent(value) : 'Нет данных';
}

function Indicators({ detail }: { detail: BondDetail }) {
  const s = detail.securities;
  const m = detail.marketdata;
  const desc = detail.bond_description;
  const kind = String(s.BONDTYPE43 ?? '');
  const couponType = /купон|дисконт/i.test(kind) ? kind : s.COUPONTYPE ?? desc?.coupon_details;
  const currency = String(s.FACEUNIT ?? '').replace(/^SUR$/, 'RUB');
  const terms = useCouponTerms(detail);
  const yesNo = (flag: unknown) => flag === true || flag === 1 ? 'Да' : flag === false || flag === 0 ? 'Нет' : 'Нет данных';
  const rows = [
    ['Тип купона', display(couponType)],
    ['Ставка купона', percentage(s.COUPONPERCENT)],
    ...(terms.hasFloatingRate ? [
      ['Базовый актив', display(terms.base)],
      ['Надбавка к базовой ставке', display(terms.spread)],
    ] : []),
    ['Купонный период, дней', display(terms.period)],
    ['Накопленный купонный доход на бумагу', typeof s.ACCRUEDINT === 'number' ? formatNumber(s.ACCRUEDINT, 2) + ' ' + currency : 'Нет данных'],
    ['Ближайший купон', formatDate(typeof s.NEXTCOUPON === 'string' ? s.NEXTCOUPON : null)],
    ['Купон', typeof s.COUPONVALUE === 'number' ? formatNumber(s.COUPONVALUE, 2) + ' ' + currency : 'Нет данных'],
    ['Погашение', formatDate(typeof s.MATDATE === 'string' ? s.MATDATE : null)],
    ['Оферта', offerType(detail)],
    ['Погашение номинала частями', yesNo(amortization(detail))],
    ['Был дефолт', yesNo(desc?.hasdefault)],
    ['Был технический дефолт', yesNo(desc?.hastechnicaldefault)],
  ];
  const risk = [desc?.hasdefault, desc?.hastechnicaldefault].some(flag => flag === true || flag === 1);
  return <>
    {risk && <Alert severity="warning">По выпуску отмечен дефолт или технический дефолт</Alert>}
    <Box sx={{ display:'grid', gridTemplateColumns:'repeat(3,minmax(0,1fr))', gap:1 }}>
      {[
        ['Доходность', percentage(m?.YIELD ?? s.YIELDATPREVWAPRICE)],
        ['Цена, % номинала', percentage(m?.LAST ?? s.PREVPRICE)],
        ['Рейтинг', display(s.RATING_LEVEL)],
      ].map(([label,value]) => <Box key={label} sx={{ bgcolor:'#edf5ff', p:1.25, borderRadius:2 }}>
        <Typography variant="caption">{label}</Typography><Typography fontWeight={700}>{value}</Typography>
      </Box>)}
    </Box>
    <Box component="dl" sx={{ m:0 }}>{rows.map(([label,value]) =>
      <Box key={label} sx={{ display:'grid',gridTemplateColumns:'1fr 1.2fr',gap:1,borderBottom:'1px solid #e1e9f2',py:1 }}>
        <Typography component="dt" color="text.secondary">{label}</Typography>
        <Typography component="dd" sx={{ m:0,textAlign:'right',fontWeight:600 }}>{value}</Typography>
      </Box>)}</Box>
  </>;
}

function Preview({ id }: { id:string }) {
  const navigate = useNavigate();
  const location = useLocation();
  const background = location.state?.tableLocation;
  const close = () => background ? navigate(-1) : navigate('/?view=bonds', {replace:true});
  const [detail,setDetail] = useState<BondDetail | null>(null);
  const [issuer, setIssuer] = useState<EmitentInfo | null>(null);
  const [error,setError] = useState(false);
  const [schedule, setSchedule] = useState<Record<string, Set<number>> | null>(null);
  const [year, setYear] = useState('');
  const [calendarError,setCalendarError] = useState(false);
  useEffect(() => {
    let active = true;
    getEmitentBySecid(id).then(value => {
      if (active) setIssuer(value);
    }).catch(() => {
      if (active) setIssuer(null);
    });
    fetchBondDetail(id).then(value => { if(active) setDetail(value); })
      .catch(() => { if(active) setError(true); });
    fetchBondCoupons(id).then(({coupons}) => {
      if (!active) return;
      const byYear: Record<string, Set<number>> = {};
      for (const coupon of coupons) {
        const date = coupon.coupondate?.match(/^(\d{4})-(0[1-9]|1[0-2])-\d{2}(?:$|T)/);
        if (date) (byYear[date[1]] ??= new Set()).add(Number(date[2]));
      }
      const years = Object.keys(byYear).sort();
      const current = String(new Date().getFullYear());
      setYear(years.find(y => y >= current) ?? years.at(-1) ?? '');
      setSchedule(byYear);
    }).catch(() => { if(active) setCalendarError(true); });
    return () => { active=false; };
  },[id]);
  const href = '/bonds/'+encodeURIComponent(id);
  return <Drawer anchor="right" open onClose={close} PaperProps={{role:'dialog','aria-modal':true,'aria-labelledby':'preview-title',sx:{width:450,maxWidth:'100%',bgcolor:'#f6f9fe'}}}>
    <Stack spacing={2} sx={{p:3,flex:1}}>
      <Box sx={{display:'flex',alignItems:'start',justifyContent:'space-between'}}>
        <Box><Typography variant="caption" color="text.secondary">Краткая карточка</Typography>
          <Typography id="preview-title" variant="h5" fontWeight={700}>{String(detail?.securities.SHORTNAME || detail?.securities.SECNAME || id)}</Typography>
          <BondIdentity secid={id} detail={detail} issuer={issuer} /></Box>
        <IconButton onClick={close} aria-label="Закрыть краткую карточку"><CloseIcon/></IconButton>
      </Box>
      {detail ? <Indicators detail={detail}/> : <Typography role="status">{error?'Не удалось загрузить параметры выпуска':'Загрузка параметров…'}</Typography>}
      <Box><Typography variant="subtitle1" fontWeight={700}>Месяцы купонных выплат</Typography>
        {schedule && year ? <>
          <Box component="label" sx={{ display: 'flex', alignItems: 'center', gap: 1, my: 1 }}>
            Год выплат
            <Box component="select" value={year} onChange={event => setYear(event.target.value)}
              sx={{ font: 'inherit', border: '1px solid #c6d6e8', borderRadius: 1, px: 1, bgcolor: 'white' }}>
              {Object.keys(schedule).sort().map(y => <option key={y}>{y}</option>)}
            </Box>
          </Box>
          <Box component="ul" aria-label={`Купоны за ${year} год`}
            sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0.75, listStyle: 'none', p: 0, m: 0 }}>
            {Array.from({ length: 12 }, (_, i) => {
              const month = new Date(2000, i, 1).toLocaleDateString('ru-RU', { month: 'short' });
              const pays = schedule[year].has(i + 1);
              return <Chip component="li" key={i} size="small" variant={pays ? 'filled' : 'outlined'}
                color={pays ? 'primary' : 'default'} label={pays ? '✓ ' + month : month}
                aria-label={month + (pays ? ' — предусмотрена выплата' : ' — выплаты в графике нет')} />;
            })}
          </Box>
          <Typography variant="caption" color="text.secondary">✓ Месяц выплаты по графику</Typography>
        </> : <Typography color="text.secondary">{calendarError ? 'Не удалось загрузить график' : schedule ? 'В графике нет дат купонов' : 'Загрузка графика…'}</Typography>}
      </Box>
    </Stack>
    <Stack spacing={1} sx={{p:2,borderTop:'1px solid #dbe6f2',bgcolor:'white'}}>
      <Button component={Link} to={href} replace={Boolean(background)} state={background?{tableLocation:background}:null} variant="contained">Подробная карточка</Button>
      <Button component="a" href={href} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNewIcon/>}>Открыть в новой вкладке</Button>
    </Stack>
  </Drawer>;
}

export default function BondPreview() {
  const { id } = useParams();
  return id ? <Preview key={id} id={id}/> : null;
}
