import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

export type HelpSection = 
  | 'comparison-bonds'
  | 'spread-analysis'
  | 'bonds-table'
  | 'zerocupon'
  | 'forecast'
  | 'macro-dashboard'
  | 'ruonia'
  | 'keyrate'
  | 'portfolio'
  | 'default';

interface HelpDialogProps {
  open: boolean;
  onClose: () => void;
  section: HelpSection;
}

/**
 * HelpDialog Component
 * 
 * Displays help content for different sections of the application
 */
export const HelpDialog: React.FC<HelpDialogProps> = ({ open, onClose, section }) => {
  const renderHelpContent = () => {
    switch (section) {
      case 'comparison-bonds':
        return (
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Introduction */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                📊 Обзор раздела
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                Раздел <strong>"Сравнение облигаций"</strong> позволяет сравнивать выбранные облигации по ключевым параметрам и рассчитывать возможные денежные потоки от инвестиций.
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                Раздел состоит из двух вкладок:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem', mb: 0.5 }}>
                  <strong>Сравнение облигаций</strong> — таблица с основными параметрами для сравнения
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                  <strong>Расчет возможных денежных потоков</strong> — прогноз доходности с учетом изменения процентных ставок
                </Typography>
              </Box>
            </Box>

            {/* How to add bonds */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                ➕ Как добавить облигации к сравнению
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                Есть несколько способов добавить облигации к сравнению:
              </Typography>
              <Box component="ol" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  <strong>Из таблицы скринера:</strong> В основной таблице облигаций найдите столбец <strong>"Добавить к сравнению"</strong> и нажмите на иконку <strong>➕</strong> рядом с нужной облигацией. Иконка изменится на <strong>❌</strong>, что означает, что облигация добавлена.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  <strong>Из файла:</strong> Нажмите кнопку <strong>"Загрузить из файла"</strong> в верхней части раздела. Поддерживаются файлы в формате JSON: экспорт портфеля (только SECID) или экспорт портфеля с полными данными. Из файла извлекаются SECID облигаций, актуальные данные подгружаются из базы.
                </Typography>
              </Box>
            </Box>

            {/* Tab 1: Comparison */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                📋 Вкладка "Сравнение облигаций"
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                В этой вкладке отображается таблица со следующими колонками:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>🗑️ Действия</strong> — кнопка для удаления облигации из сравнения
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📝 Название</strong> — краткое название облигации
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>🏷️ Тикер</strong> — идентификатор облигации (SECID)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📅 Срок до погашения, лет</strong> — срок до погашения облигации в годах
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>💵 Доходность купона относительно номинала (%)</strong> — купонная ставка в процентах годовых
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>💰 Цена (%)</strong> — текущая чистая цена в процентах от номинала
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📈 Доходность к погашению, YTM (%)</strong> — доходность к погашению (Yield to Maturity)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📊 Доходность купона к текущей цене (%)</strong> — отношение купонной ставки к текущей цене (текущая доходность)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>⏱️ Дюрация</strong> — дюрация Маколея (средневзвешенный срок до получения денежных потоков, в годах). Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📉 Модифицированная дюрация</strong> — мера чувствительности цены к изменению процентных ставок. Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📐 Выпуклость</strong> — показатель точности оценки изменения цены с помощью дюрации. Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>🔄 Изменение цены при росте / снижении ставки на 1%</strong> — прогноз изменения цены при изменении ставок на ±1%. Формат: <strong>потеря при росте / прибыль при снижении</strong>. Красный — потери, зеленый — прибыль.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📊 Премии и отклонения по рынку</strong> — разница между доходностью облигации и доходностью кривой КБД на срок дюрации Маколея. Положительные (зеленый) — премия, отрицательные (красный) — дисконт.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📈 G-спред</strong> — разница между фактической доходностью облигации и теоретической по кривой КБД с учетом всех купонов.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📉 Z-спред</strong> — постоянная спред-премия к кривой КБД для получения текущей цены. Рассчитывается только для облигаций с фиксированным купоном без встроенных опционов.
                </Typography>
              </Box>
              <Typography variant="body1" color="text.secondary" sx={{ mt: 2, fontSize: '1rem' }}>
                <strong>💡 Совет:</strong> Наведите курсор на иконку <strong>ℹ️</strong> рядом с названием колонки, чтобы увидеть подробное описание показателя.
              </Typography>
            </Box>

            {/* Tab 2: Cash Flow */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                💰 Вкладка "Расчет возможных денежных потоков"
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                Вкладка позволяет рассчитать прогноз доходности с учетом изменения процентных ставок. Пока параметры не заданы, отображается сообщение <strong>"Заполните все поля для расчета"</strong>. Порядок действий:
              </Typography>
              <Box component="ol" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Нажмите <strong>"Параметры расчета"</strong> (кнопка доступна на этой вкладке).
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Задайте параметры: <strong>Сумма инвестиций, руб.</strong>, <strong>Горизонт расчета, лет</strong>, <strong>Предполагаемая ставка, %</strong>, <strong>Текущая ставка ЦБ, %</strong>. При необходимости включите <strong>"Использовать ставку из прогноза Банка России"</strong> — тогда предполагаемая ставка подставится из прогноза.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Нажмите <strong>"Применить"</strong>. После этого появится таблица результатов. Пересчет <strong>не выполняется автоматически</strong>: при изменении параметров в диалоге, ручной цены или НКД нужно нажать кнопку <strong>"Пересчитать"</strong> над таблицей результатов.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Опция <strong>"Задать параметры вручную"</strong>: при включении в таблице результатов становятся редактируемыми колонки <strong>"Чистая цена, %"</strong> и <strong>"НКД, руб."</strong>. Двойной щелчок по ячейке → ввод значения → <strong>Enter</strong> для сохранения. После изменений нажмите <strong>"Пересчитать"</strong>.
                </Typography>
              </Box>
              <Typography variant="body1" color="text.secondary" sx={{ mt: 2, mb: 1, fontSize: '1rem' }}>
                В таблице результатов отображаются:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Название</strong>, <strong>Тикер</strong>, <strong>Чистая цена, %</strong>, <strong>НКД, руб.</strong> (при ручном вводе — редактируемые), <strong>Купонная ставка</strong>, <strong>Модифицированная дюрация</strong>
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Чистая цена, руб.</strong>, <strong>Грязная цена покупки, руб.</strong> — цена покупки с учетом НКД
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Количество лотов</strong> — сколько лотов можно купить на указанную сумму
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Остаток, руб.</strong> — неинвестированный остаток суммы
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Полная сумма купонов (включая НКД в первом купоне), руб.</strong> — все купонные выплаты за период владения
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Чистый доход от купонов (за вычетом уплаченного НКД), руб.</strong> — доход от купонов по методу Dirty-to-Dirty
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Изменение цены, %</strong>, <strong>Прогнозная цена, %</strong> — прогноз изменения цены с учетом дюрации и выпуклости
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Выручка от продажи (грязная цена), руб.</strong> — сумма от продажи облигаций по грязной цене
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Итоговая сумма, руб.</strong> — выручка от продажи + чистый доход от купонов + остаток
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Абсолютная прибыль, руб.</strong> — разница между итоговой суммой и затратами на покупку (метод Dirty-to-Dirty)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Совокупная доходность (Total Return), %</strong> — процентная доходность инвестиции
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Среднегодовая доходность (CAGR), %</strong> — среднегодовая доходность с учетом сложного процента
                </Typography>
              </Box>
            </Box>

            {/* Export functions */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                💾 Экспорт данных
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                Экспорт доступен только на вкладке <strong>"Сравнение облигаций"</strong> при наличии данных:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Сохранить в CSV</strong> — экспорт таблицы сравнения в CSV для Excel и других программ
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Сохранить в Markdown</strong> — экспорт таблицы сравнения в Markdown для документирования
                </Typography>
              </Box>
            </Box>

            {/* Tips */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                💡 Полезные советы
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Сравнивайте облигации с похожим сроком до погашения для более точного анализа
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Обращайте внимание на дюрацию — она показывает чувствительность облигации к изменению ставок
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Положительный спред означает, что облигация торгуется с премией к кривой КБД
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Используйте расчет денежных потоков для оценки потенциальной доходности при различных сценариях изменения ставок
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Расчет денежных потоков выполняется методом Dirty-to-Dirty с корректным учетом НКД при покупке и продаже
                </Typography>
              </Box>
            </Box>

            {/* Important notes */}
            <Box sx={{ bgcolor: 'info.light', p: 2, borderRadius: 1 }}>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                ⚠️ Важные замечания
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Показатели «Премии и отклонения по рынку», G-спред, Z-спред и Выпуклость рассчитываются только для облигаций с фиксированным купоном без встроенных опционов
                </Typography>
                <Typography component="li" variant="body1" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Расчеты основаны на текущих данных и являются прогнозными оценками
                </Typography>
                <Typography component="li" variant="body1" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  Реальная доходность может отличаться от расчетной из-за изменения рыночных условий
                </Typography>
              </Box>
            </Box>
          </Box>
        );

      case 'macro-dashboard':
        return (
          <Box sx={{
            px: { xs: 1.5, md: 2.5 },
            py: { xs: 1.5, md: 2 },
            display: 'flex',
            flexDirection: 'column',
            gap: 1.25,
            bgcolor: '#F4F7FD',
            color: '#526c8d',
            fontFamily: 'var(--app-font-family)',
            '& p, & li': { fontFamily: 'var(--app-font-family)', fontSize: '0.9375rem', lineHeight: 1.6 },
            '& strong': { color: '#17345b', fontWeight: 700 },
          }}>
            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.7 }}>Как читать макроэкономический обзор</Typography>
              <Typography component="p" sx={{ m: 0 }}>
                Дашборд собирает опубликованные макроэкономические ряды в одном месте и отдельно показывает автоматическую оценку их динамики. Сначала смотрите на дату каждого наблюдения и полноту данных, затем — на направление нескольких независимых показателей. Оценка описывает аргументы, которые видны в данных; она не предсказывает решение Банка России.
              </Typography>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>1. Порядок работы</Typography>
              <Box component="ol" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.45 }}>Нажмите кнопку обновления в правой части заголовка, если хотите заново запросить данные. Внизу дашборда показано время формирования ответа; у показателей и графиков могут быть более ранние даты публикации.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}>Просмотрите шесть верхних карточек. Это последние доступные значения основных ставок, инфляции и ожиданий. Под крупным числом указано сопоставление, а внизу — дата наблюдения или решения.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}>Сравните линии на четырёх графиках. Нажмите на график или на значок раскрытия, чтобы открыть увеличенный вид и задать даты начала и конца периода. В модальном окне доступны только даты, для которых есть наблюдения. Наведение на точку показывает подсказку; шкала по вертикали подбирается по диапазону данных и может начинаться выше нуля.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}>Затем откройте карточки «Автоматическая оценка»: прочитайте статус, долю доступных данных и подсказку «Метрики, вошедшие в оценку». Счётчики ↑, ↓ и • показывают количество ускоряющихся, замедляющихся и стабильных метрик.</Typography>
                <Typography component="li">В блоке «Баланс сигналов» проверьте итоговый индекс, покрытие и вес каждой группы. При статусе «Недостаточно данных» не трактуйте пустой индекс как ноль.</Typography>
              </Box>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>2. Верхние карточки: что означает каждое число</Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Ключевая ставка</strong> — действующая ставка Банка России. Под ней показано изменение относительно предыдущего решения, а не изменение за месяц.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Инфляция за 12 месяцев</strong> — изменение общего уровня потребительских цен за последние 12 месяцев, рассчитанное по месячным индексам цен. Стрелка под значением сравнивает темп с предыдущим месячным наблюдением.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Инфляция за месяц</strong> — изменение цен за последний опубликованный месяц. Само число — месячный темп; подпись под ним показывает, насколько этот темп изменился по сравнению с предыдущим месячным наблюдением.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Ожидания инфляции, 1 год</strong> — опубликованная оценка ожидаемой инфляции на годовом горизонте. Стрелка показывает изменение оценки относительно предыдущего месячного наблюдения.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Устойчивая инфляция</strong> — модифицированный показатель базовой (устойчивой) инфляции из аналитического ряда проекта. Он помогает оценить более устойчивую часть ценового давления, сглаживая часть разовых и волатильных изменений; это отдельная оценка, а не полная инфляция.</Typography>
                <Typography component="li"><strong>RUONIA</strong> — ставка однодневного межбанковского денежного рынка. Под ней показан спред <strong>RUONIA − ключевая ставка</strong>: положительное число означает, что RUONIA выше ключевой ставки, отрицательное — ниже. Это разница ставок в процентных пунктах.</Typography>
              </Box>
              <Typography component="p" sx={{ mt: 1.1, mb: 0 }}>
                Числа со знаком <strong>%</strong> — уровни ставок или темпы инфляции. Изменения, спреды и разрывы со знаком <strong>п.п.</strong> — разность двух процентных уровней. Например, переход с 10% на 10,5% — это +0,5 п.п., а не рост на 0,5%.
              </Typography>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>3. Графики: линии, периоды и сравнение</Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Инфляция.</strong> Две линии за последние 12 месячных наблюдений: темп за месяц и темп за 12 месяцев. Краткосрочный месячный темп может колебаться сильнее годового.</Typography>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Инфляционные ожидания.</strong> Фактическая инфляция за 12 месяцев сопоставляется с ожиданиями на горизонте 1 года и 5 лет. Разрывы под заголовком графика рассчитываются как «ожидание минус фактическая инфляция»: положительный разрыв означает более высокие ожидания, отрицательный — более низкие. Это сопоставление уровней, не сигнал автоматического повышения или снижения ставки.</Typography>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Денежно-кредитные условия.</strong> Ключевая ставка и RUONIA показаны за последние шесть месяцев. Метка «Спред» — последнее доступное значение RUONIA минус ключевая ставка. Ключевая ставка меняется решениями, а RUONIA наблюдается чаще, поэтому между ними возможны временные расхождения.</Typography>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Кривая доходности ОФЗ.</strong> Здесь ровно две линии-снимка: текущая кривая и кривая на ближайшую доступную дату примерно 30 дней назад. По горизонтали отложены <strong>12 сроков погашения</strong>: 3, 6 и 9 месяцев, 1, 2, 3, 5, 7, 10, 15, 20 и 30 лет; по вертикали — доходность в процентах годовых. То есть каждая линия соединяет доходности по всем этим срокам на одну дату. В увеличенном виде выбранный календарный интервал сравнивает первый и последний доступные снимки в нём. Под обычным графиком отдельно приводится изменение за 30 дней для сроков 2, 5 и 10 лет. Отсутствующие наблюдения не интерполируются и могут оставлять разрыв.</Typography>
              </Box>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>4. Как формируются оценки по четырём направлениям</Typography>
              <Typography component="p" sx={{ mt: 0, mb: 0.8 }}>
                Для каждой метрики рассчитывается изменение в процентных пунктах. Если оно больше порога, метрика получает сигнал <strong>+1</strong> (рост или ускорение); если меньше минус порог — <strong>−1</strong> (снижение или замедление); в пределах порога — <strong>0</strong> (значимого изменения нет). Если сопоставимых наблюдений недостаточно, метрика пропускается: ей не присваивается нулевой сигнал.
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Инфляция.</strong> Учитываются месячный и 12-месячный темпы, недельная инфляция, трендовая инфляция за 3 и 5 лет и модифицированная базовая инфляция. Для месячных рядов сравниваются средние за последние 3 календарных месяца и предыдущие 3; для недельной инфляции — последние 4 наблюдения и предшествующие 4. Пороги: месяц <strong>0,10 п.п.</strong>, 12 месяцев <strong>0,15 п.п.</strong>, неделя <strong>0,03 п.п.</strong>, каждый тренд и модифицированная базовая — <strong>0,10 п.п.</strong>. Веса по порядку: <strong>25%, 15%, 15%, 15%, 15%, 15%</strong>.</Typography>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Инфляционные ожидания.</strong> В оценку входят ожидания на 1 и 5 лет. Для каждого ряда сравниваются средние за последние 3 месяца с предыдущими 3 месяцами; порог — <strong>0,20 п.п.</strong>. Веса: <strong>60%</strong> у горизонта 1 год и <strong>40%</strong> у горизонта 5 лет. Фактическая инфляция и разрывы ожиданий с ней служат контекстом и напрямую в балл этого направления не входят.</Typography>
                <Typography component="li" sx={{ mb: 0.55 }}><strong>Денежно-кредитные условия.</strong> Учитываются изменения за 30 дней RUONIA, ключевой ставки и спреда RUONIA − ключевая ставка. Для каждого действует порог <strong>0,10 п.п.</strong>; веса — <strong>50%, 30% и 20%</strong> соответственно. Рост краткосрочных ставок соответствует ужесточению, снижение — смягчению. Сама по себе высокая ставка без её изменения не создаёт сигнал ужесточения за период.</Typography>
                <Typography component="li"><strong>Рынок ОФЗ.</strong> Учитываются изменения доходности ОФЗ сроком 2, 5 и 10 лет за 30 дней. Порог для каждой — <strong>0,15 п.п.</strong>; веса — <strong>40%, 35% и 25%</strong>. Рост доходностей классифицируется как рост рыночных доходностей, снижение — как их снижение. Доходность ОФЗ отражает рыночные ожидания и премии за риск, поэтому её движение само по себе не доказывает будущего решения ЦБ.</Typography>
              </Box>
              <Typography component="p" sx={{ mt: 1.1, mb: 0 }}>
                Балл направления — среднее сигналов <strong>с учётом весов только доступных метрик</strong>, в диапазоне от −1 до +1. Покрытие — доля веса, для которой удалось получить сигнал. Минимум для вывода: инфляция <strong>60%</strong>, ожидания <strong>40%</strong>, денежно-кредитные условия <strong>50%</strong>, рынок ОФЗ <strong>60%</strong>. Ниже минимума выводится «Недостаточно данных». При исходных настройках направленный статус ставится от <strong>+0,30</strong> или до <strong>−0,30</strong>. «Смешанная динамика» появляется, когда не менее <strong>20%</strong> доступного веса направлено вверх и не менее <strong>20%</strong> — вниз, а модуль балла меньше 0,30. В остальных случаях балл между −0,30 и +0,30 трактуется как стабильная динамика.
              </Typography>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>5. Итоговый индекс и баланс аргументов</Typography>
              <Typography component="p" sx={{ mt: 0, mb: 0.7 }}>
                Общий индекс — среднее баллов доступных направлений с весами: инфляция <strong>35%</strong>, ожидания <strong>25%</strong>, денежно-кредитные условия <strong>20%</strong>, рынок ОФЗ <strong>20%</strong>. Если направление недоступно, его вес исключается и оставшиеся веса нормируются. Для показа индекса покрытие общей суммы весов должно быть не ниже <strong>60%</strong>.
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.45 }}>Индекс <strong>от −1 до −0,30 включительно</strong>: преобладают дезинфляционные аргументы, согласующиеся со снижением ставки.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}>Индекс <strong>от +0,30 включительно до +1</strong>: преобладают инфляционные аргументы, согласующиеся с повышением ставки.</Typography>
                <Typography component="li">Между порогами <strong>−0,30 и +0,30</strong> нет выраженного преобладания: сигналы близки к нейтральным или разнонаправлены.</Typography>
              </Box>
              <Typography component="p" sx={{ mt: 0.9, mb: 0 }}>
                Полосы «Аргументы за снижение / сохранение / повышение» группируют доступные направления по знаку их балла: отрицательный, нулевой или положительный. Подписи показывают число направлений, сумму их настроенных весов и долю от веса классифицированных направлений. Доли описывают структуру учтённых весов, <strong>а не вероятности</strong> решения ЦБ. Для итогового индекса также используется порог <strong>0,30</strong>: значения от −0,30 до +0,30 не показывают выраженного преобладания. Этот и остальные пороги и веса задаются в настройках макродашборда.
              </Typography>
            </Paper>

            <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, borderRadius: 2.25, borderColor: '#e1eaf5', bgcolor: '#fff' }}>
              <Typography component="h2" sx={{ color: '#17345b', fontSize: '1rem', fontWeight: 700, lineHeight: 1.35, textTransform: 'none', mb: 0.8 }}>6. Как трактовать цвета, пропуски и ограничения</Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>Красный / стрелка вверх</strong> означает рост показателя или инфляционного давления в пределах конкретного индикатора; <strong>зелёный / стрелка вниз</strong> — снижение или замедление; серый — стабильность либо нейтральный индикатор; оранжевый может обозначать смешанную картину. Для ставок цвет не означает «хорошо» или «плохо» для инвестора.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}><strong>«—» и пропуски</strong> возникают, если источник ещё не опубликовал значение, ряду не хватает непрерывной истории для сравнения или наблюдение слишком старое. Пропуски не заменяются нулями и не должны читаться как отсутствие инфляции или неизменность ставки.</Typography>
                <Typography component="li" sx={{ mb: 0.45 }}>У разных источников разные даты публикации и частота обновления. Сравнивайте дату рядом с числом; карточка может быть актуальнее или старше другой карточки.</Typography>
                <Typography component="li">Все пороги, веса направлений, веса отдельных метрик и требования к покрытию можно менять на странице <strong>«Настройки»</strong>. В справке приведены исходные значения конфигурации. Изменение настроек меняет классификацию и итоговый индекс, но не сами опубликованные наблюдения.</Typography>
              </Box>
              <Alert severity="info" variant="outlined" sx={{ mt: 1.2, bgcolor: '#f7faff', borderColor: '#dce8f6', color: '#526c8d', '& .MuiAlert-icon': { color: '#3977c3' } }}>
                <Typography component="p" sx={{ m: 0, color: 'inherit', fontSize: '0.9rem !important' }}>
                  <strong>Важно:</strong> автоматическая оценка — прозрачная сводка выбранных индикаторов и настроенных порогов. Индекс не является вероятностью, инвестиционной рекомендацией или официальным прогнозом Банка России; учитывайте контекст, пересмотры статистики и новые публикации.
                </Typography>
              </Alert>
            </Paper>
          </Box>
        );

      default:
        return (
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
              📚 Помощь
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
              Раздел помощи для данного раздела находится в разработке.
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
              Скоро здесь появится подробное описание функциональности этого раздела.
            </Typography>
          </Box>
        );
    }
  };

  const getTitle = () => {
    switch (section) {
      case 'comparison-bonds':
        return 'Помощь: Сравнение облигаций';
      case 'spread-analysis':
        return 'Помощь: Анализ спредов';
      case 'bonds-table':
        return 'Помощь: Таблица облигаций';
      case 'zerocupon':
        return 'Помощь: Кривая бескупонной доходности';
      case 'forecast':
        return 'Помощь: Прогноз ставок';
      case 'macro-dashboard':
        return 'Помощь: Макроэкономический обзор';
      case 'ruonia':
        return 'Помощь: RUONIA';
      case 'keyrate':
        return 'Помощь: Ключевая ставка';
      case 'portfolio':
        return 'Помощь: Портфель';
      default:
        return 'Помощь';
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="paper"
      PaperProps={section === 'macro-dashboard' ? {
        sx: {
          borderRadius: 2.5,
          border: '1px solid #e1eaf5',
          boxShadow: '0 16px 48px rgba(23, 52, 91, 0.18)',
          overflow: 'hidden',
          fontFamily: 'var(--app-font-family)',
        },
      } : undefined}
    >
      <DialogTitle sx={section === 'macro-dashboard' ? {
        px: { xs: 2, md: 3 },
        py: 1.75,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        color: '#10264a',
        fontFamily: 'var(--app-font-family)',
        fontSize: '1.1rem',
        fontWeight: 700,
        letterSpacing: '0.005em',
        textTransform: 'none',
        bgcolor: '#fff',
        borderBottom: '1px solid #e1eaf5',
      } : { fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.25rem' }}>
        <InfoIcon sx={section === 'macro-dashboard' ? { color: '#3977c3', fontSize: 20 } : undefined} color={section === 'macro-dashboard' ? undefined : 'primary'} />
        {getTitle()}
      </DialogTitle>
      <DialogContent sx={section === 'macro-dashboard' ? {
        p: 0,
        bgcolor: '#F4F7FD',
        fontFamily: 'var(--app-font-family)',
        '&:first-of-type': { pt: 0 },
      } : { fontSize: '1rem' }}>
        {renderHelpContent()}
      </DialogContent>
      <DialogActions sx={section === 'macro-dashboard' ? {
        px: { xs: 2, md: 3 },
        py: 1.25,
        bgcolor: '#fff',
        borderTop: '1px solid #e1eaf5',
      } : undefined}>
        <Button onClick={onClose} variant={section === 'macro-dashboard' ? 'outlined' : 'contained'} sx={section === 'macro-dashboard' ? {
          px: 2.25,
          borderColor: '#d5e2f1',
          color: '#29476f',
          fontFamily: 'var(--app-font-family)',
          fontWeight: 650,
          borderRadius: 1.5,
          '&:hover': { borderColor: '#9fb6d2', bgcolor: '#f7faff' },
        } : { fontSize: '1rem' }}>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};



