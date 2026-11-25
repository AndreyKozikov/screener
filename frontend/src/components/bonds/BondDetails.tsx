import { useLocation, useNavigate, useParams } from 'react-router-dom';
import React, { useEffect, useState } from 'react';
import { Dialog, Tooltip } from '@mui/material';
import { ShowChart, Percent, Payments, Event, AccountBalance, Layers, Verified } from '@mui/icons-material';
import { fetchBondDetail, fetchBondsCoupons } from '../../api/bonds';
import { fetchDescriptions, type DescriptionsResponse } from '../../api/metadata';
import { getEmitentBySecid, type EmitentInfo } from '../../api/emitent';
import { getWorstRating, getRatingLevel, getRatingAgency, type Rating } from '../../utils/ratings';
import { formatDate, formatNumber, formatPercent, formatTradingStatus } from '../../utils/formatters';
import type { BondDetail, BondFieldValue } from '../../types/bond';
import type { Coupon } from '../../types/coupon';
import { useUiStore } from '../../stores/uiStore';
import { CouponsTable } from './CouponsTable';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import './BondDetails.css';

type FieldDescriptionMap = Record<string, string>;

const isoDateRegex = /^\d{4}-\d{2}-\d{2}/;
const isoDateTimeRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:/;
const numericPattern = /^-?\d+(?:[.,]\d+)?$/;
const percentKeywords = ['PERCENT', 'YIELD', 'RATE', 'SPREAD'];
const zeroDecimalKeywords = ['SIZE', 'VOLUME', 'COUNT', 'LOT', 'NUM', 'NUMBER', 'PERIOD', 'QUANTITY'];
const currencyKeywords = ['VALUE', 'PRICE', 'AMOUNT', 'SUM', 'CAPITAL', 'COST', 'VOLTODAY', 'VALTODAY', 'WAPRICE', 'LAST', 'BID', 'OFFER'];

const formatNumericValue = (fieldUpper: string, numericValue: number): string => {
  if (!Number.isFinite(numericValue)) {
    return '-';
  }

  if (percentKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatPercent(numericValue);
  }

  if (currencyKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 2);
  }

  if (zeroDecimalKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 0);
  }

  return formatNumber(numericValue, Math.abs(numericValue) < 1 ? 4 : 2);
};

const formatFieldValue = (field: string, rawValue: BondFieldValue): string => {
  if (rawValue === null || rawValue === undefined) {
    return '—';
  }

  if (Array.isArray(rawValue)) {
    const formatted = rawValue
      .map((value) => formatFieldValue(field, value as BondFieldValue))
      .filter((value) => value !== '—');

    return formatted.length > 0 ? formatted.join(', ') : '—';
  }

  if (typeof rawValue === 'boolean') {
    return rawValue ? 'Да' : 'Нет';
  }

  if (typeof rawValue === 'string' && (!field || ['INN','ISIN','SECID','REGNUMBER','regnumber','programregistrynumber','BOARDID'].includes(field))) return rawValue || '—';
  const fieldUpper = field.toUpperCase();
  if (typeof rawValue === 'number' && fieldUpper.endsWith('SPREADBP')) return formatNumber(rawValue, 2) + ' б. п.';
  if (['hasdefault','hastechnicaldefault','hasprospectus','isqualifiedinvestors'].includes(field) && (rawValue === 0 || rawValue === 1)) return rawValue ? 'Да' : 'Нет';

  if (typeof rawValue === 'number') {
    return formatNumericValue(fieldUpper, rawValue);
  }

  if (typeof rawValue === 'string') {
    const trimmed = rawValue.trim();

    if (trimmed.length === 0 || trimmed.toLowerCase() === 'nan') {
      return '—';
    }

    if (fieldUpper.includes('DATE') || isoDateRegex.test(trimmed) || isoDateTimeRegex.test(trimmed)) {
      return formatDate(trimmed);
    }

    if (numericPattern.test(trimmed)) {
      const parsed = Number(trimmed.replace(',', '.'));
      return formatNumericValue(fieldUpper, parsed);
    }

    return trimmed;
  }

  return String(rawValue);
};

const flattenDescriptions = (descriptions: DescriptionsResponse): FieldDescriptionMap => {
  const result: FieldDescriptionMap = {};

  Object.values(descriptions).forEach((section) => {
    if (section && typeof section === 'object' && !Array.isArray(section)) {
      Object.entries(section).forEach(([field, description]) => {
        if (typeof description === 'string' && description.trim().length > 0) {
          result[field] = description;
        }
      });
    }
  });

  return result;
};


type Field = [string, BondFieldValue | undefined, string];
const sections = ["Эмитент и риски", "Купоны и погашение", "Доходность и дюрация", "Цены и торги", "Паспорт выпуска", "Биржевые данные"] as const;
const tones = ['#1769bd','#147468','#80539b','#445fa5','#226c87','#675c95','#447348'];
const icons = [ShowChart, Percent, Payments, Event, AccountBalance, Layers, Verified];

export function BondDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const close = () => location.state?.tableLocation ? navigate(-1) : navigate('/?view=bonds', { replace: true });
  return <Dialog fullScreen open onClose={close} aria-labelledby="bond-title">
    {id && <Details key={id} id={id} onClose={close} />}
  </Dialog>;
}

function Details({id,onClose}:{id:string;onClose:()=>void}) {
  const [detail,setDetail] = useState<BondDetail | null>(null);
  const [issuer,setIssuer] = useState<EmitentInfo | null>(null);
  const [error,setError] = useState('');
  const [section,setSection] = useState<string>(sections[0]);
  const [tips,setTips] = useState<FieldDescriptionMap>({});
  const [coupons,setCoupons] = useState<Coupon[] | null>(null);
  const [couponError,setCouponError] = useState('');
  const [year,setYear] = useState('');
  const refresh = useUiStore(state => state.triggerDataRefresh);
  useEffect(() => {
    let current = true;
    fetchBondDetail(id).then(value => {if(current) setDetail(value)}).catch(() => {if(current) setError('Не удалось загрузить данные выпуска')});
    getEmitentBySecid(id).then(value => {if(current) setIssuer(value)}).catch(() => {});
    fetchDescriptions().then(value => {if(current) setTips(flattenDescriptions(value))}).catch(() => {});
    return () => {current=false};
  },[id]);
  useEffect(() => {
    if(section !== sections[1] || coupons || couponError) return;
    let current=true;
    fetchBondsCoupons([id]).then(result => {
      if (!current) return;
      const rows=result.get(id)?.coupons ?? [];
      setCoupons(rows);
      if(rows.length) refresh();
    }).catch(() => {if(current) setCouponError('Не удалось загрузить купоны')});
    return () => {current=false};
  },[id,section,coupons,couponError,refresh]);
  const header=<header><button onClick={onClose} aria-label="Закрыть карточку и вернуться">← Назад</button><span>Центр управления</span></header>;
  if(!detail) return <div className="bond-page">{header}<h1 id="bond-title">Карточка облигации</h1>{error?<ErrorMessage message={error}/>:<LoadingSpinner message="Загрузка выпуска…"/>}</div>;
  const securities=detail.securities, market=detail.marketdata, yields=detail.marketdata_yields?.[0] ?? {}, description=detail.bond_description ?? {};
  const ratings=Array.isArray(securities.RATINGS)?securities.RATINGS.filter(v=>v && typeof v==='object') as unknown as Rating[]:[];
  const rating=getWorstRating(ratings);
  const issuerRating=getWorstRating(issuer?.cci_rating_companies ?? []);
  const bondRating=[getRatingLevel(rating) ?? securities.RATING_LEVEL,getRatingAgency(rating) ?? securities.RATING_AGENCY].filter(Boolean).join(' · ');
  const issuerGrade=[getRatingLevel(issuerRating),getRatingAgency(issuerRating)].filter(Boolean).join(' · ');
  const lot=typeof securities.LOTSIZE==='number' && typeof securities.FACEVALUE==='number'?securities.LOTSIZE*securities.FACEVALUE:securities.LOTVALUE;
  const statuses:Record<string,string>={A:'Выпуск в обращении',S:'Торги приостановлены',D:'Выпуск погашен',N:'Выпуск неактивен'};
  const status=statuses[String(securities.STATUS)] ?? 'Статус не указан';
  const groups: Record<string,Record<string,Field[]>> = {
    'Эмитент и риски': {
      'Эмитент и рейтинги': [
        ['Эмитент', issuer?.emitent_title, ''],
        ['ИНН', detail.emitent_inn ?? issuer?.emitent_inn, 'INN'],
        ['Рейтинг выпуска', bondRating, ''],
        ['Рейтинг эмитента', issuerGrade, ''],
        ['Статус бумаги', status, ''],
      ],
      'Дефолты и ограничения': [
        ['Был дефолт', description.hasdefault, 'hasdefault'],
        ['Был технический дефолт', description.hastechnicaldefault, 'hastechnicaldefault'],
        ['Только для квалифицированных инвесторов', description.isqualifiedinvestors, 'isqualifiedinvestors'],
      ],
    },
    'Купоны и погашение': {
      'Купон': [
        ['Ставка купона', securities?.COUPONPERCENT, 'COUPONPERCENT'],
        ['Период', securities?.COUPONPERIOD, 'COUPONPERIOD'],
        ['Сумма на бумагу', securities?.COUPONVALUE, 'COUPONVALUE'],
        ['НКД', securities?.ACCRUEDINT, 'ACCRUEDINT'],
        ['Следующий купон', securities?.NEXTCOUPON, 'NEXTCOUPON'],
        ['Бенчмарк купона', description.coupon_benchmark, 'coupon_benchmark'],
        ['Надбавка к бенчмарку, п.п.', description.coupon_benchmark_spread, 'coupon_benchmark_spread'],
        ['Условия купона', description.coupon_details, 'coupon_details'],
      ],
      'Погашение и досрочный выкуп': [
        ['Погашение', securities?.MATDATE, 'MATDATE'],
        ['Оферта', securities?.OFFERDATE, 'OFFERDATE'],
        ['Пут-опцион', securities?.PUTOPTIONDATE, 'PUTOPTIONDATE'],
        ['Колл-опцион', securities?.CALLOPTIONDATE, 'CALLOPTIONDATE'],
        ['Дней до погашения (данные MOEX)', description.daystoredemption, 'daystoredemption'],
        ['Амортизация', securities.BONDTYPE43 == null ? null : String(securities.BONDTYPE43) === '1', ''],
        ['Цена выкупа', securities?.BUYBACKPRICE, 'BUYBACKPRICE'],
      ],
    },
    'Доходность и дюрация': {
      'Показатели доходности': [
        ['К погашению', market?.YIELD ?? yields?.EFFECTIVEYIELD ?? securities?.YIELDATPREVWAPRICE, 'YIELD'],
        ['К оферте', market?.YIELDTOOFFER ?? yields?.YIELDTOOFFER, 'YIELDTOOFFER'],
        ['К колл-опциону', market?.CALLOPTIONYIELD, 'CALLOPTIONYIELD'],
        ['Эффективная доходность', yields?.EFFECTIVEYIELD, 'EFFECTIVEYIELD'],
        ['Эффективная по средневзвешенной цене', yields?.EFFECTIVEYIELDWAPRICE, 'EFFECTIVEYIELDWAPRICE'],
        ['Доходность по предыдущей средневзвешенной цене', securities.YIELDATPREVWAPRICE, ''],
      ],
      'Спреды': [
        ['G-спред', yields?.GSPREADBP, 'GSPREADBP'],
        ['Z-спред', yields?.ZSPREADBP, 'ZSPREADBP'],
      ],
      'Дюрация': [
        ['Дюрация', market?.DURATION ?? yields?.DURATION, 'DURATION'],
        ['Дюрация к колл-опциону', market?.CALLOPTIONDURATION, 'CALLOPTIONDURATION'],
        ['По средневзвешенной цене', yields?.DURATIONWAPRICE ?? securities?.DURATIONWAPRICE, 'DURATIONWAPRICE'],
      ],
      'Основание расчёта': [
        ['Дата, к которой рассчитана доходность', yields?.YIELDDATE ?? securities?.BUYBACKDATE, 'YIELDDATE'],
        ['Дата расчёта от эмитента', securities?.DATEYIELDFROMISSUER, 'DATEYIELDFROMISSUER'],
        ['Тип даты доходности', yields?.YIELDDATETYPE, 'YIELDDATETYPE'],
      ],
    },
    'Цены и торги': {
      'Цены сделок': [
        ['Текущая рыночная', market?.LCURRENTPRICE, 'LCURRENTPRICE'],
        ['Последняя сделка', market?.LAST, 'LAST'],
        ['Закрытие', market?.LCLOSEPRICE, 'LCLOSEPRICE'],
        ['Предыдущее официальное закрытие', securities?.PREVLEGALCLOSEPRICE, 'PREVLEGALCLOSEPRICE'],
        ['Открытие', market?.OPEN, 'OPEN'],
        ['Цена предыдущей сессии', securities.PREVPRICE, ''],
        ['Рыночная цена 2', market?.MARKETPRICE2, 'MARKETPRICE2'],
      ],
      'Средняя цена и динамика': [
        ['Средневзвешенная', market?.WAPRICE ?? yields?.WAPRICE, 'WAPRICE'],
        ['Предыдущая средневзвешенная', securities?.PREVWAPRICE, 'PREVWAPRICE'],
        ['Последняя к предыдущему дню', market?.LASTTOPREVPRICE, 'LASTTOPREVPRICE'],
        ['Последняя к средневзвешенной', market?.LASTCNGTOLASTWAPRICE, 'LASTCNGTOLASTWAPRICE'],
        ['Средневзвешенная к предыдущему дню', market?.WAPTOPREVWAPRICEPRCNT, 'WAPTOPREVWAPRICEPRCNT'],
        ['Последняя к предыдущей сделке', market?.LASTCHANGEPRCNT, 'LASTCHANGEPRCNT'],
      ],
      'Спрос и предложение': [
        ['Лучшая покупка', market?.BID, 'BID'],
        ['Лучшая продажа', market?.OFFER, 'OFFER'],
        ['Максимальная покупка', market?.HIGHBID, 'HIGHBID'],
        ['Минимальная продажа', market?.LOWOFFER, 'LOWOFFER'],
        ['Спред', market?.SPREAD, 'SPREAD'],
        ['Совокупный объём предложений', market?.OFFERDEPTHT, 'OFFERDEPTHT'],
      ],
      'Объём торгов': [
        ['Количество сделок', market?.NUMTRADES, 'NUMTRADES'],
        ['Объём торгов', market?.VOLTODAY, 'VOLTODAY'],
        ['Объём последней сделки', market?.QTY, 'QTY'],
        ['Стоимость последней сделки', market?.VALUE, 'VALUE'],
        ['Оборот за день', market?.VALTODAY, 'VALTODAY'],
      ],
      'Сессия и режим торгов': [
        ['Торговая сессия', market?.TRADINGSESSION, 'TRADINGSESSION'],
        ['Статус торгов', formatTradingStatus(typeof market?.TRADINGSTATUS === "string" ? market.TRADINGSTATUS : null), 'TRADINGSTATUS'],
        ['Режим торгов', securities?.BOARDNAME, 'BOARDNAME'],
        ['Код рынка', securities?.MARKETCODE, 'MARKETCODE'],
        ['Размер лота', securities.LOTSIZE, ''],
        ['Номинал лота', lot, ''],
      ],
    },
    'Паспорт выпуска': {
      'Идентификаторы': [
        ['Наименование', securities?.SECNAME, 'SECNAME'],
        ['Краткое название', securities?.SHORTNAME, 'SHORTNAME'],
        ['ISIN', securities?.ISIN, 'ISIN'],
        ['Регистрационный номер', securities.REGNUMBER ?? description.regnumber, 'REGNUMBER'],
        ['Тип бумаги', securities?.SECTYPE, 'SECTYPE'],
        ['Вид облигации', securities?.BONDTYPE43, 'BONDTYPE43'],
        ['Полное название выпуска', description.issuename, 'issuename'],
        ['Номер программы', description.programregistrynumber, 'programregistrynumber'],
      ],
      'Номинал и объём размещения': [
        ['Номинал', securities?.FACEVALUE, 'FACEVALUE'],
        ['Валюта номинала', securities?.FACEUNIT, 'FACEUNIT'],
        ['Валюта расчётов', securities?.CURRENCYID, 'CURRENCYID'],
        ['Объём выпуска', securities?.ISSUESIZE, 'ISSUESIZE'],
        ['Бумаг в обращении', securities?.ISSUESIZEPLACED, 'ISSUESIZEPLACED'],
        ['Номинал на дату расчётов', securities?.FACEVALUEONSETTLEDATE, 'FACEVALUEONSETTLEDATE'],
        ['Тип номинала', description.facevalue_type, 'facevalue_type'],
        ['Текущий номинал', description.facevalue, 'facevalue'],
        ['Первоначальный номинал', description.initialfacevalue, 'initialfacevalue'],
        ['Валюта номинала', description.faceunit, 'faceunit'],
        ['Размер выпуска, бумаг', description.issuesize, 'issuesize'],
      ],
      'Регистрация и условия': [
        ['Тип облигации', description.bond_type, 'bond_type'],
        ['Опцион / подтип', description.bond_subtype, 'bond_subtype'],
        ['Дата выпуска', description.issuedate, 'issuedate'],
        ['Дата погашения', description.matdate, 'matdate'],
        ['Есть проспект', description.hasprospectus, 'hasprospectus'],
        ['Дата решения о выпуске', description.decisiondate, 'decisiondate'],
        ['Дата регистрации', description.registry_date, 'registry_date'],
      ],
    },
    'Биржевые данные': {
      'Коды и обновление данных': [
        ['Код бумаги', securities.SECID, 'SECID'],
        ['Номер обновления', market?.SEQNUM ?? yields.SEQNUM, 'SEQNUM'],
        ['Примечание', securities.REMARKS, 'REMARKS'],
        ['Маркер КБД', yields.ZCYCMOMENT, 'ZCYCMOMENT'],
        ['Знаков после запятой', securities.DECIMALS, 'DECIMALS'],
        ['Код режима', securities.BOARDID ?? market?.BOARDID, 'BOARDID'],
      ],
    },
  };
  const price=securities.PREVPRICE ?? securities.PREVWAPRICE ?? market?.LAST;
  const income=securities.YIELDATPREVWAPRICE ?? market?.YIELD;
  const money=(v:BondFieldValue|undefined)=>v==null?'—':formatFieldValue('VALUE',v)+' '+String(securities.FACEUNIT ?? '');
  const metrics=[['Цена, % номинала',formatFieldValue('PRICE',price ?? null)],['Доходность',formatFieldValue('YIELD',income ?? null)],['НКД',money(securities.ACCRUEDINT)],['Погашение',formatFieldValue('MATDATE',securities.MATDATE)],['Номинал',money(securities.FACEVALUE)],['Лот',money(lot)],['Рейтинг',bondRating || issuerGrade || '—']];
  const years=Array.from(new Set(coupons?.map(c=>c.coupondate?.slice(0,4)).filter(Boolean))).sort();
  const next=typeof securities.NEXTCOUPON==='string'?Date.parse(securities.NEXTCOUPON):NaN;
  const days=Math.max(0,Math.ceil((next-Date.now())/86400000));
  return <div className="bond-page">{header}<main>
    <section className="hero"><small>Рынок облигаций / Карточка облигации</small>
      <h1 id="bond-title">{String(securities.SHORTNAME || securities.SECNAME || id)}</h1><span className="chip">{status}</span>
      <p>{String(securities.SECNAME || '')}</p><small>{[issuer?.emitent_title,detail.emitent_inn && 'ИНН '+detail.emitent_inn,securities.ISIN && 'ISIN '+securities.ISIN,securities.REGNUMBER && 'Рег. № '+securities.REGNUMBER].filter(Boolean).join(' · ')}</small>
      <div><a href={'https://www.moex.com/ru/issue.aspx?board='+encodeURIComponent(String(securities.BOARDID || 'TQCB'))+'&code='+encodeURIComponent(id)} target="_blank" rel="noreferrer">Выпуск на MOEX ↗</a></div>
      <div className="metrics">{metrics.map(([label,value],i)=>{const Icon=icons[i];return <div key={label} className="metric" style={{'--tone':tones[i]} as React.CSSProperties}><span className="kpi-icon"><Icon/></span><small>{label}</small><b>{value}</b></div>})}</div>
      <div className="risks">{[securities.OFFERDATE && 'Оферта', (securities.CALLOPTIONDATE || securities.PUTOPTIONDATE) && 'Досрочное погашение',String(securities.BONDTYPE43)==='1' && 'Амортизация',[true,1].includes(description.hasdefault as boolean|number) && 'Отмечен дефолт',[true,1].includes(description.hastechnicaldefault as boolean|number) && 'Отмечен технический дефолт'].filter(Boolean).map(label=><span key={String(label)}>{String(label)}</span>)}</div>
    </section>
    <section className="work"><div className="bar"><h2>{section}</h2></div>
    <div className="layout"><aside>{sections.map(n=><button key={n} aria-current={n===section} onClick={()=>setSection(n)}>{n}</button>)}</aside>
    <div className="cards" style={{'--tone':tones[[6,3,1,0,4,5][sections.findIndex(n=>n===section)]]} as React.CSSProperties}>
    {Object.entries(groups[section]).map(([title,fields])=><article key={title}><h3>{title}</h3><dl>{fields.map(([label,value,key])=><div className="row" key={label+key}><dt>{tips[key]?<Tooltip title={tips[key]}><span tabIndex={0}>{label} ⓘ</span></Tooltip>:label}</dt><dd>{formatFieldValue(key,value ?? null)}</dd></div>)}</dl>{title==='Купон' && Number.isFinite(days) && typeof securities.COUPONPERIOD==='number' && securities.COUPONPERIOD>0 && <><small>Дней до купона: {days}</small><progress aria-label="Купонный период" max={securities.COUPONPERIOD} value={Math.max(0,securities.COUPONPERIOD-days)}/></>}</article>)}
    {section===sections[1] && <article className="calendar"><h3>Календарь выплат</h3><label>Год <select value={year} onChange={e=>setYear(e.target.value)}><option value="">Все годы</option>{years.map(y=><option key={y}>{y}</option>)}</select></label><CouponsTable coupons={(coupons ?? []).filter(c=>!year || c.coupondate?.startsWith(year))} isLoading={!coupons && !couponError} error={couponError || null}/></article>}
    </div></div></section></main></div>;
}
