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

const typeLabels: Record<string, string> = {
  exchange_bond: 'Биржевая', ofz_bond: 'ОФЗ', corporate_bond: 'Корпоративная',
  municipal_bond: 'Муниципальная', subfederal_bond: 'Региональная',
};

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
    ['Тип облигации', typeLabels[String(s.BONDTYPE)] ?? display(desc?.bond_type ?? s.BONDTYPE)],
    ['Тип купона', display(couponType)],
    ['Ставка купона', percentage(s.COUPONPERCENT)],
    ...(terms.hasFloatingRate ? [
      ['От какой ставки или индекса зависит купон', display(terms.base)],
      ['Надбавка к базовой ставке', display(terms.spread)],
    ] : []),
    ['Купонный период, дней', display(terms.period)],
    ['Накопленный купонный доход на бумагу', typeof s.ACCRUEDINT === 'number' ? formatNumber(s.ACCRUEDINT, 2) + ' ' + currency : 'Нет данных'],
    ['Ближайший купон', formatDate(typeof s.NEXTCOUPON === 'string' ? s.NEXTCOUPON : null)],
    ['Выплата на бумагу', typeof s.COUPONVALUE === 'number' ? formatNumber(s.COUPONVALUE, 2) + ' ' + currency : 'Нет данных'],
    ['Погашение', formatDate(typeof s.MATDATE === 'string' ? s.MATDATE : null)],
    ['Оферта', formatDate(typeof s.OFFERDATE === 'string' ? s.OFFERDATE : null)],
    ['Право эмитента на досрочное погашение', formatDate(typeof s.CALLOPTIONDATE === 'string' ? s.CALLOPTIONDATE : null)],
    ['Право инвестора на досрочный выкуп', formatDate(typeof s.PUTOPTIONDATE === 'string' ? s.PUTOPTIONDATE : null)],
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
  const [months,setMonths] = useState<number[] | null>(null);
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
      const numbers = coupons.flatMap(coupon => {
        const match = coupon.coupondate?.match(/^\d{4}-(0[1-9]|1[0-2])-\d{2}(?:$|T)/);
        return match ? [Number(match[1])] : [];
      });
      if (active) setMonths([...new Set(numbers)].sort((a, b) => a - b));
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
        {months?.length ? <Stack direction="row" useFlexGap flexWrap="wrap" gap={0.75} mt={1}>{months.map(n=>
          <Chip key={n} label={new Date(2000,n-1,1).toLocaleDateString('ru-RU',{month:'long'})} size="small"/>)}</Stack>
          : <Typography color="text.secondary">{calendarError?'Не удалось загрузить график':months?'В графике нет дат купонов':'Загрузка графика…'}</Typography>}
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
