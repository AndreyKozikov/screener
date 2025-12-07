/**
 * Bond data interfaces matching backend Pydantic models
 */

// Simplified bond for table display
export interface BondListItem {
  SECID: string;
  BOARDID: string;
  SHORTNAME: string;
  COUPONPERCENT: number | null;
  MATDATE: string | null;  // ISO date string
  STATUS: string | null;
  TRADINGSTATUS: string | null;
  FACEVALUE: number | null;
  PREVPRICE: number | null;
  YIELDATPREVWAPRICE: number | null;
  NEXTCOUPON: string | null;  // ISO date string
  BOARDNAME: string | null;
  CALLOPTIONDATE: string | null;  // ISO date string
  PUTOPTIONDATE: string | null;  // ISO date string
  ACCRUEDINT: number | null;  // НКД (накопленный купонный доход)
  COUPONPERIOD: number | null;  // Длительность купона в днях
  COUPONVALUE: number | null;  // Сумма купона в рублях из данных о купонных выплатах
  DURATION: number | null;  // Дюрация
  DURATIONWAPRICE: number | null;  // Дюрация по средневзвешенной цене в днях
  CURRENCYID: string | null;  // Валюта торговли
  FACEUNIT: string | null;  // Валюта номинала
  LISTLEVEL: number | null;  // Уровень листинга
  RATING_AGENCY: string | null;  // Название рейтингового агентства
  RATING_LEVEL: string | null;  // Уровень рейтинга
  BONDTYPE: string | null;  // Тип облигации
  COUPON_TYPE: string | null;  // Тип купона (FIX или FLOAT)
}

// Detailed bond information
export type BondPrimitive = string | number | boolean | null;
export type BondFieldValue = BondPrimitive | BondPrimitive[];

export interface BondSecurity {
  SECID: string;
  BOARDID: string;
  SHORTNAME: string;
  SECNAME: string | null;
  PREVWAPRICE: number | null;
  YIELDATPREVWAPRICE: number | null;
  COUPONVALUE: number | null;
  COUPONPERCENT: number | null;
  NEXTCOUPON: string | null;
  ACCRUEDINT: number | null;
  PREVPRICE: number | null;
  LOTSIZE: number | null;
  FACEVALUE: number | null;
  BOARDNAME: string | null;
  STATUS: string | null;
  MATDATE: string | null;
  ISIN: string | null;
  REGNUMBER: string | null;
  CURRENCYID: string | null;
  // Additional fields
  [key: string]: BondFieldValue;
}

export interface BondMarketData {
  SECID: string;
  BOARDID: string;
  BID: number | null;
  OFFER: number | null;
  SPREAD: number | null;
  LAST: number | null;
  LASTCHANGE: number | null;
  LASTCHANGEPRCNT: number | null;
  WAPRICE: number | null;
  TRADINGSTATUS: string | null;
  // Additional fields
  [key: string]: BondFieldValue;
}

export interface BondDetail {
  securities: Record<string, BondFieldValue>;
  marketdata: Record<string, BondFieldValue> | null;
  marketdata_yields: Array<Record<string, BondFieldValue>> | null;
}

// Portfolio bond with quantity
export interface PortfolioBond extends BondListItem {
  quantity: number; // Количество облигаций (целое число > 0)
}
