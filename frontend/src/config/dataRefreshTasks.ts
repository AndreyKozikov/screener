export type DataRefreshTaskId =
  | 'bonds'
  | 'zerocupon'
  | 'ratings'
  | 'emitents'
  | 'coupons'
  | 'currency'
  | 'ruonia'
  | 'keyrate'
  | 'trading-history'
  | 'forecast'
  | 'floaters'
  | 'ipc'
  | 'ipc-weekly'
  | 'inflation-expectations'
  | 'inflation';

export interface DataRefreshTaskDefinition {
  id: DataRefreshTaskId;
  dialogLabel: string;
  statusLabel: string;
}

// Порядок пунктов совпадает с диалогом обновления данных на главной странице.
export const DATA_REFRESH_TASKS: DataRefreshTaskDefinition[] = [
  { id: 'bonds', dialogLabel: 'Обновить данные облигаций', statusLabel: 'Данные облигаций' },
  {
    id: 'zerocupon',
    dialogLabel: 'Обновить данные кривой бескупонной доходности',
    statusLabel: 'Кривая бескупонной доходности',
  },
  { id: 'ratings', dialogLabel: 'Обновить рейтинги', statusLabel: 'Рейтинги' },
  { id: 'emitents', dialogLabel: 'Обновить эмитентов', statusLabel: 'Эмитенты' },
  { id: 'coupons', dialogLabel: 'Обновить купоны', statusLabel: 'Купоны' },
  { id: 'currency', dialogLabel: 'Обновить курсы валют', statusLabel: 'Курсы валют' },
  { id: 'ruonia', dialogLabel: 'Обновить данные ставки RUONIA', statusLabel: 'Ставка RUONIA' },
  { id: 'keyrate', dialogLabel: 'Обновить ключевую ставку ЦБ', statusLabel: 'Ключевая ставка ЦБ' },
  { id: 'trading-history', dialogLabel: 'Обновить историю торгов', statusLabel: 'История торгов' },
  {
    id: 'forecast',
    dialogLabel: 'Обновить среднесрочный прогноз Банка России',
    statusLabel: 'Среднесрочный прогноз Банка России',
  },
  { id: 'floaters', dialogLabel: 'Обновить данные по флоатерам', statusLabel: 'Данные по флоатерам' },
  {
    id: 'ipc',
    dialogLabel: 'Обновить индексы потребительских цен (ИПЦ Росстата)',
    statusLabel: 'ИПЦ Росстата',
  },
  { id: 'ipc-weekly', dialogLabel: 'Обновить еженедельный ИПЦ', statusLabel: 'Еженедельный ИПЦ' },
  {
    id: 'inflation-expectations',
    dialogLabel: 'Обновить инфляционные ожидания',
    statusLabel: 'Инфляционные ожидания',
  },
  { id: 'inflation', dialogLabel: 'Обновление данных по инфляции', statusLabel: 'Данные по инфляции' },
];
