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
                  <strong>Из файла:</strong> Нажмите кнопку <strong>"Загрузить из файла"</strong> в верхней части раздела. Поддерживаются файлы экспорта портфеля в формате JSON (как с полными данными, так и только с SECID).
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
                  <strong>🗑️ Удалить</strong> — кнопка для удаления облигации из сравнения
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📝 Название</strong> — краткое название облигации
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>🏷️ Тикер</strong> — идентификатор облигации (SECID)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📅 Погашение</strong> — дата погашения облигации
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>💰 Цена</strong> — текущая чистая цена облигации в процентах от номинала
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📈 YTM</strong> — доходность к погашению (Yield to Maturity)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>💵 Купон</strong> — размер купонной ставки в процентах годовых
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📊 Купон к цене</strong> — отношение купонной ставки к текущей цене (показывает текущую доходность)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>⏱️ Дюрация Маколея</strong> — средневзвешенный срок до получения денежных потоков (в годах). Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📉 Модифицированная дюрация</strong> — мера чувствительности цены облигации к изменению процентных ставок. Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📐 Выпуклость</strong> — показатель, показывающий точность оценки изменения цены с помощью дюрации. Наведите на заголовок для подробной информации.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>🔄 Изменение цены</strong> — прогнозируемое изменение цены при изменении ставок на ±1%. Формат: <strong>потеря при росте ставок / прибыль при снижении ставок</strong>. Красный цвет — потери, зеленый — прибыль.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📊 Spread</strong> — разница между доходностью облигации и доходностью кривой бескупонной доходности (КБД) на срок, равный дюрации Маколея. Положительные значения (зеленый) — премия, отрицательные (красный) — дисконт.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📈 G-Spread</strong> — разница между фактической доходностью облигации и теоретической доходностью, рассчитанной на основе кривой КБД с учетом всех купонов.
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>📉 Z-Spread</strong> — постоянная спред-премия, добавляемая к кривой КБД для получения текущей цены облигации. Рассчитывается только для облигаций с фиксированным купоном без встроенных опционов.
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
                Эта вкладка позволяет рассчитать прогноз доходности инвестиций с учетом изменения процентных ставок. Для начала работы:
              </Typography>
              <Box component="ol" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Нажмите кнопку <strong>"Параметры расчета"</strong> в верхней части раздела
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  Задайте параметры:
                  <Box component="ul" sx={{ mt: 0.5, pl: 3 }}>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                      <strong>Сумма инвестиций</strong> — сколько вы планируете инвестировать (в рублях)
                    </Typography>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                      <strong>Горизонт расчета</strong> — на сколько лет вы планируете инвестировать
                    </Typography>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                      <strong>Предполагаемая ставка</strong> — прогнозируемая ключевая ставка ЦБ (можно использовать прогноз Банка России, установив соответствующую галочку)
                    </Typography>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                      <strong>Текущая ставка ЦБ</strong> — текущая ключевая ставка Центрального банка
                    </Typography>
                  </Box>
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                  При необходимости включите опцию <strong>"Задать параметры вручную"</strong> для редактирования цены и НКД каждой облигации. После включения этой опции:
                  <Box component="ul" sx={{ mt: 0.5, pl: 3 }}>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem', mb: 0.5 }}>
                      В таблице результатов станут доступны для редактирования колонки <strong>"Чистая цена, %"</strong> и <strong>"НКД, руб."</strong>
                    </Typography>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem', mb: 0.5 }}>
                      Для редактирования значения сделайте <strong>двойной щелчок</strong> по ячейке с нужным параметром
                    </Typography>
                    <Typography component="li" variant="body1" color="text.secondary" sx={{ fontSize: '1rem' }}>
                      Введите новое значение и нажмите клавишу <strong>Enter</strong> для сохранения изменений
                    </Typography>
                  </Box>
                </Typography>
              </Box>
              <Typography variant="body1" color="text.secondary" sx={{ mt: 2, mb: 1, fontSize: '1rem' }}>
                В таблице результатов отображаются:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Количество облигаций</strong> — сколько облигаций можно купить на указанную сумму
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Грязная цена покупки</strong> — цена покупки с учетом НКД
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Купоны</strong> — сумма купонных выплат за период владения
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Изменение цены</strong> — прогнозируемое изменение цены облигации с учетом дюрации и выпуклости
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Выручка от продажи</strong> — сумма, которую вы получите при продаже облигаций
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Итоговая сумма</strong> — общая сумма, которую вы получите (выручка + купоны + остаток)
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Абсолютная прибыль</strong> — разница между итоговой суммой и затратами на покупку
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Совокупная доходность (Total Return)</strong> — процентная доходность инвестиции
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Среднегодовая доходность (CAGR)</strong> — среднегодовая доходность с учетом сложного процента
                </Typography>
              </Box>
            </Box>

            {/* Export functions */}
            <Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600, fontSize: '1.25rem' }}>
                💾 Экспорт данных
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1, fontSize: '1rem' }}>
                В разделе доступны функции экспорта:
              </Typography>
              <Box component="ul" sx={{ mt: 1, pl: 3 }}>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Сохранить в CSV</strong> — экспорт таблицы сравнения в формат CSV для открытия в Excel или других программах
                </Typography>
                <Typography component="li" variant="body1" color="text.secondary" sx={{ mb: 0.5, fontSize: '1rem' }}>
                  <strong>Сохранить в Markdown</strong> — экспорт таблицы сравнения в формат Markdown для документирования
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
                  При расчете денежных потоков учитывается метод Dirty-to-Dirty, который корректно учитывает НКД при покупке и продаже
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
                  Некоторые показатели (Spread, G-Spread, Z-Spread, Выпуклость) рассчитываются только для облигаций с фиксированным купоном без встроенных опционов
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
