import type { BondFilters } from '../types/filters';

/**
 * Вспомогательные функции для «глубокой ссылки» из чата агента на страницу
 * рынка облигаций (вкладка «Рынок облигаций» главной страницы) с применёнными
 * фильтрами поиска.
 *
 * URL-параметры используют имена канонического словаря фильтров бэкенда
 * (BondsListFiltersDTO): yield_min, rating_min, matdate_from, bondtype43 и т.д.
 */

const QUERY_MARKER = 'view';
const QUERY_MARKER_VALUE = 'bonds';

const KEY_TO_FILTER: Record<string, keyof BondFilters> = {
  coupon_min: 'couponMin',
  coupon_max: 'couponMax',
  yield_min: 'yieldMin',
  yield_max: 'yieldMax',
  coupon_yield_min: 'couponYieldMin',
  coupon_yield_max: 'couponYieldMax',
  matdate_from: 'matdateFrom',
  matdate_to: 'matdateTo',
  coupon_months: 'couponMonths',
  listlevel: 'listlevel',
  faceunit: 'faceunit',
  bondtype: 'bondtype',
  bondtype43: 'bondtype43',
  rating_min: 'ratingMin',
  rating_max: 'ratingMax',
  search: 'search',
};

const NUMBER_KEYS = new Set([
  'coupon_min',
  'coupon_max',
  'yield_min',
  'yield_max',
  'coupon_yield_min',
  'coupon_yield_max',
]);
const NUMBER_ARRAY_KEYS = new Set(['coupon_months', 'listlevel', 'bondtype', 'bondtype43']);
const STRING_ARRAY_KEYS = new Set(['faceunit']);

/**
 * Разбирает location.search на фильтры рынка облигаций.
 * Возвращает null, если в URL нет маркера `view=bonds` или не распознан ни один параметр.
 */
export const parseMarketFiltersUrl = (search: string): Partial<BondFilters> | null => {
  if (!search) return null;
  const params = new URLSearchParams(search);
  if (params.get(QUERY_MARKER) !== QUERY_MARKER_VALUE) {
    return null;
  }

  const partial: Record<string, unknown> = {};
  const keys = Object.keys(KEY_TO_FILTER).filter((key) => params.has(key));

  for (const key of keys) {
    // Значения массивов могут прийти как повторяющиеся ключи (doseq-формат
    // urlencode с бэкенда) или как один ключ с запятыми — объединяем всё.
    const values = params.getAll(key);
    if (values.length === 0) continue;
    const raw = values.join(',');
    const filterKey = KEY_TO_FILTER[key];
    if (NUMBER_KEYS.has(key)) {
      const num = Number(raw);
      if (Number.isFinite(num)) partial[filterKey] = num;
    } else if (NUMBER_ARRAY_KEYS.has(key)) {
      partial[filterKey] = raw
        .split(',')
        .map((item) => Number(item.trim()))
        .filter((item) => Number.isFinite(item));
    } else if (STRING_ARRAY_KEYS.has(key)) {
      partial[filterKey] = raw
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    } else {
      partial[filterKey] = raw;
    }
  }

  return Object.keys(partial).length > 0 ? (partial as Partial<BondFilters>) : null;
};
