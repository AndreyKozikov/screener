/**
 * TypeScript типы данных ИПЦ (Индексы потребительских цен)
 */

export interface IpcMonthItem {
  ипц: string;
  'продовольстенные товары': string;
  'непродовольственные товары': string;
  услуги: string;
}

export type IpcYearData = Record<string, IpcMonthItem>;

export type IpcData = Record<string, IpcYearData>;

export interface IpcLoadResponse {
  status: string;
  output_path: string;
  years_count: number;
  total_months_count: number;
  data: IpcData;
}



