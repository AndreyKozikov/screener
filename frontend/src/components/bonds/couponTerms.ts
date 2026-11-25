import { useEffect, useState } from 'react';
import { fetchFloatParamsBySecid } from '../../api/bonds';
import type { BondDetail } from '../../types/bond';
import type { BondFloatParamsDTO } from '../../types/bondFloatParams';

export const indicatorNames: Record<string, string> = {
  RREFKEYR: 'Ключевая ставка Банка России',
  RUONIA_IND: 'Индекс RUONIA',
  RUONIA3M: 'Срочная ставка RUONIA на 3 месяца',
  RUONIA6M: 'Срочная ставка RUONIA на 6 месяцев',
  ZR_YLD_CRV: 'Кривая бескупонной доходности (КБД)',
  OTHER: 'Прочий индикатор',
  KEY_RATE: 'Ключевая ставка ЦБ РФ',
  RUONIA: 'Ставка RUONIA (межбанковские кредиты)',
  RUSFAR: 'Ставка RUSFAR (рынок репо)',
  CPI: 'Индекс потребительских цен (инфляция)',
  GCURVE: 'Доходность гособлигаций (ОФЗ)',
  CUSTOM: 'Индивидуальный индикатор',
};

export function amortization(detail: BondDetail) {
  const kind = String(detail.securities.BONDTYPE43 ?? '');
  const nominal = String(detail.bond_description?.facevalue_type ?? '');
  if (/неамортиз|без амортизации|постоянн/i.test(nominal)) return false;
  if (kind === '1' || /амортизируем/i.test(kind + ' ' + nominal)) return true;
  return null;
}

export function useCouponTerms(detail: BondDetail | null) {
  const desc = detail?.bond_description;
  const kind = String(detail?.securities.BONDTYPE43 ?? '');
  const indicator = String(desc?.coupon_benchmark ?? '').trim();
  const hasFloatingRate = kind === '6' || /плавающ/i.test(kind) || Boolean(indicator);
  const id = String(detail?.securities.SECID ?? '');
  const [params, setParams] = useState<BondFloatParamsDTO | null>(null);
  useEffect(() => {
    if (!id || !hasFloatingRate) return;
    let current = true;
    fetchFloatParamsBySecid(id).then(result => {
      if (current && result.is_find) setParams(result);
    }).catch(() => {
      // При отсутствии параметров используем сведения из описания выпуска.
    });
    return () => { current = false; };
  }, [id, hasFloatingRate]);
  const fallback = params?.secid === id ? params : null;
  const base = [indicator, fallback?.base_indicator_code].reduce<string | null>((name, raw) => {
    if (name || !raw) return name;
    const value = raw.trim();
    return /[а-яё]/i.test(value) ? value : indicatorNames[value.toUpperCase()] ?? null;
  }, null);
  const rawSpread = desc?.coupon_benchmark_spread ?? fallback?.spread;
  const spread = typeof rawSpread === 'number' || (typeof rawSpread === 'string' && rawSpread.trim())
    ? Number(String(rawSpread).replace(',', '.')) : NaN;
  return {
    hasFloatingRate,
    base,
    spread: Number.isFinite(spread) ? spread.toLocaleString('ru-RU', {maximumFractionDigits: 4}) + ' п.п.' : null,
    period: detail?.securities.COUPONPERIOD ?? fallback?.coupon_frequency_days,
  };
}
