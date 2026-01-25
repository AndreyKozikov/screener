import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

export type HelpSection = 
  | 'comparison-bonds'
  | 'spread-analysis'
  | 'bonds-table'
  | 'zerocupon'
  | 'forecast'
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
    >
      <DialogTitle sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.25rem' }}>
        <InfoIcon color="primary" />
        {getTitle()}
      </DialogTitle>
      <DialogContent sx={{ fontSize: '1rem' }}>
        {renderHelpContent()}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} variant="contained" sx={{ fontSize: '1rem' }}>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
};
