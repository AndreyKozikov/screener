import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Tabs,
  Tab,
  Chip,
  Divider,
  Stack,
} from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import ClearIcon from '@mui/icons-material/Clear';
import { useFiltersStore } from '../../stores/filtersStore';
import { useBondsStore } from '../../stores/bondsStore';
import {
  CouponRangeFilter,
  YieldRangeFilter,
  CouponYieldRangeFilter,
  MaturityDateFilter,
  ListLevelFilter,
  CurrencyFilter,
  BondTypeFilter,
  BondType43Filter,
  RatingRangeFilter,
} from './AllFilters';

/**
 * Пропсы для компонента модального окна фильтров
 */
interface FiltersModalProps {
  open: boolean;      // Открыто ли модальное окно
  onClose: () => void; // Функция закрытия модального окна
}

/**
 * Пропсы для компонента панели вкладки
 */
interface TabPanelProps {
  children?: React.ReactNode; // Содержимое панели (фильтры)
  index: number;              // Индекс этой панели (0, 1, 2, 3)
  value: number;              // Индекс активной панели
}

/**
 * Компонент панели вкладки
 * Отображает содержимое только для активной вкладки
 * 
 * Параметры sx:
 * - height: '100%' - занимает всю доступную высоту родителя
 * - width: '100%' - занимает всю доступную ширину родителя
 * - display: flex/none - показывается только если это активная вкладка
 * - flexDirection: 'column' - элементы располагаются вертикально
 * - minHeight: 0 - позволяет сжиматься при необходимости
 * - overflow: 'hidden' - скрывает переполнение контента
 */
function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <Box
      role="tabpanel"
      hidden={value !== index}  // Скрывает панель, если она не активна
      id={`filter-tabpanel-${index}`}
      aria-labelledby={`filter-tab-${index}`}
      sx={{
        height: '100%',         // Занимает всю высоту контейнера
        width: '100%',          // Занимает всю ширину контейнера
        display: value === index ? 'flex' : 'none', // Показывается только активная панель
        flexDirection: 'column', // Вертикальное расположение элементов
        minHeight: 0,           // Минимальная высота для корректной работы flex
        overflow: 'hidden',     // Скрывает переполнение
      }}
      {...other}
    >
      {/* Рендерит содержимое только для активной вкладки */}
      {value === index && children}
    </Box>
  );
}

/**
 * Компонент модального окна фильтров
 * 
 * Структура модального окна:
 * - Левая колонка (25% ширины): вертикальные вкладки для навигации по группам фильтров
 * - Правая колонка (75% ширины): область с фильтрами выбранной группы
 * 
 * Группы фильтров:
 * 0. Доходность - фильтры по доходности купона и к погашению
 * 1. Даты - фильтры по датам погашения
 * 2. Категории - фильтры по типам, валютам, уровню листинга
 * 3. Рейтинг - фильтры по рейтингам облигаций
 */
export const FiltersModal: React.FC<FiltersModalProps> = ({ open, onClose }) => {
  // Получаем функции из хранилища фильтров
  const {
    resetFilters,
    applyFilters,
  } = useFiltersStore();
  
  // Получаем количество отфильтрованных облигаций для отображения
  const { filteredCount } = useBondsStore();

  // Состояние активной вкладки (0 = Доходность, 1 = Даты, 2 = Категории, 3 = Рейтинг)
  const [activeTab, setActiveTab] = useState(0);

  /**
   * Обработчик смены вкладки
   * @param newValue - индекс новой активной вкладки (0-3)
   */
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  /**
   * Обработчик применения фильтров
   * Применяет выбранные фильтры к данным и закрывает модальное окно
   */
  const handleApply = () => {
    applyFilters();
    onClose();
  };

  /**
   * Обработчик сброса фильтров
   * Сбрасывает все фильтры к значениям по умолчанию
   */
  const handleReset = () => {
    resetFilters();
  };

  /**
   * Обработчик отмены
   * Закрывает модальное окно без применения фильтров
   */
  const handleCancel = () => {
    onClose();
  };

  /**
   * Массив групп фильтров для навигации
   * Каждая группа соответствует одной вкладке
   */
  const filterGroups = [
    { label: 'Доходность', id: 'yield' },      // Индекс 0
    { label: 'Даты', id: 'dates' },            // Индекс 1
    { label: 'Категории', id: 'categories' },  // Индекс 2
    { label: 'Рейтинг', id: 'rating' },        // Индекс 3
  ];

  return (
    /**
     * Основной компонент диалогового окна
     * 
     * Параметры Dialog:
     * - open: открыто/закрыто модальное окно
     * - onClose: функция закрытия при клике вне окна или на ESC
     * - maxWidth="md": максимальная ширина (600px в Material-UI)
     * - fullWidth: занимает всю доступную ширину до maxWidth
     * 
     * PaperProps.sx - стили для контейнера диалога:
     * - maxHeight: '90vh' - максимальная высота 90% от высоты экрана
     * - borderRadius: '24px' - скругление углов
     * - border: рамка вокруг модального окна
     * - overflow: 'hidden' - скрывает переполнение (для скругленных углов)
     */
    <Dialog
      open={open}
      onClose={handleCancel}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: '90vh',        // Максимальная высота 90% экрана
          borderRadius: '24px',     // Скругление углов
          border: '1px solid #E2E8F0', // Рамка светло-серого цвета
          overflow: 'hidden',       // Скрывает содержимое за границами
        },
      }}
    >
      {/* Заголовок модального окна с иконкой и счетчиком найденных облигаций */}
      <DialogTitle
        sx={{
          pb: 2,                    // Отступ снизу (padding-bottom)
          pt: 3,                    // Отступ сверху (padding-top)
          px: 3,                    // Отступы слева и справа (padding-x)
          borderBottom: '1px solid', // Разделительная линия снизу
          borderColor: 'divider',   // Цвет разделителя (тема Material-UI)
        }}
      >
        {/* Контейнер заголовка: иконка с текстом слева, счетчик справа */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Левая часть: иконка фильтра и заголовок */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            {/* Иконка фильтра в цветном квадрате */}
            <Box
              sx={{
                p: 1,                        // Отступ внутри (padding)
                borderRadius: '12px',        // Скругление углов
                backgroundColor: 'primary.main', // Фон основного цвета темы
                color: 'white',              // Белый цвет иконки
                display: 'flex',
                alignItems: 'center',        // Вертикальное выравнивание по центру
                justifyContent: 'center',    // Горизонтальное выравнивание по центру
              }}
            >
              <FilterAltIcon />
            </Box>
            {/* Заголовок "ФИЛЬТРЫ" */}
            <Typography variant="h5" component="span" fontWeight={700}>
              ФИЛЬТРЫ
            </Typography>
          </Box>
          {/* Правая часть: счетчик найденных облигаций */}
          <Chip
            label={`Найдено: ${filteredCount.toLocaleString()}`} // Форматирует число с разделителями тысяч
            color="primary"
            sx={{
              fontWeight: 600,              // Жирный шрифт
              fontSize: '0.875rem',         // Размер шрифта (14px)
              height: '36px',               // Высота чипа
              px: 2,                        // Отступы слева и справа
            }}
          />
        </Box>
      </DialogTitle>

      {/* Основная область контента с фильтрами */}
      {/* 
        Параметры DialogContent:
        - dividers: показывает разделители между секциями
        - height: '650px' - фиксированная высота контентной области
        - display: 'flex', flexDirection: 'column' - вертикальная flex-структура
        - overflow: 'hidden' - скрывает переполнение
        - p: 0 - убирает внутренние отступы (padding)
      */}
      <DialogContent dividers sx={{ p: 0, overflow: 'hidden', height: '650px', display: 'flex', flexDirection: 'column' }}>
        {/* 
          Гибкая flex-структура вместо Grid:
          - display: 'flex' - горизонтальное расположение колонок
          - height: '100%' - занимает всю доступную высоту
          - minHeight: 0 - позволяет корректно работать flex-элементам
        */}
        <Box sx={{ display: 'flex', height: '100%', minHeight: 0 }}>
          {/* 
            Левая колонка навигации - фиксированная ширина
            - width: 260px - фиксированная ширина (можно настроить: 240-280px)
            - minWidth: 260px - минимальная ширина для предотвращения сжатия
            - borderRight - разделительная линия справа
            - backgroundColor: 'grey.50' - светло-серый фон
            - display: 'flex', flexDirection: 'column' - вертикальное расположение вкладок
          */}
          <Box
            sx={{
              width: 260,                    // Фиксированная ширина левой колонки
              minWidth: 260,                // Минимальная ширина (предотвращает сжатие)
              borderRight: '1px solid',      // Разделительная линия справа
              borderColor: 'divider',        // Цвет разделителя
              backgroundColor: 'grey.50',    // Светло-серый фон
              display: 'flex',
              flexDirection: 'column',       // Вертикальное расположение вкладок
            }}
          >
            {/* 
              Вертикальные вкладки для навигации по группам фильтров
              
              Параметры Tabs:
              - orientation="vertical" - вертикальное расположение вкладок
              - value={activeTab} - индекс активной вкладки (0-3)
              - onChange={handleTabChange} - обработчик смены вкладки
              - variant="scrollable" - вкладки можно прокручивать при необходимости
              - scrollButtons="auto" - кнопки прокрутки показываются автоматически
              
              Стили (.MuiTabs-indicator) - убирает стандартный индикатор активной вкладки
              
              Стили (.MuiTab-root) - стили для всех вкладок:
                - minHeight: '60px' - минимальная высота вкладки (увеличено для лучшей читаемости)
                - fontWeight: 500 - обычная толщина шрифта
                - textTransform: 'none' - не преобразует текст в верхний регистр
                - fontSize: '0.925rem' - размер шрифта (14.8px)
                - alignItems: 'flex-start' - выравнивание по левому краю
                - justifyContent: 'flex-start' - выравнивание по верхнему краю
                - pl: 3, pr: 4 - отступы слева и справа
              
              Стили (.Mui-selected) - стили для активной вкладки:
                - fontWeight: 700 - жирный шрифт
                - backgroundColor: 'background.paper' - белый фон
                - borderRight: '4px solid' - синяя полоска справа (4px, увеличено)
              
              Стили (:hover) - стили при наведении:
                - backgroundColor: 'action.hover' - светло-серый фон
            */}
            <Tabs
              orientation="vertical"
              value={activeTab}
              onChange={handleTabChange}
              variant="scrollable"
              scrollButtons="auto"
              sx={{
                '& .MuiTabs-indicator': {
                  display: 'none',           // Скрывает стандартный индикатор вкладки
                },
                '& .MuiTab-root': {
                  minHeight: '60px',          // Минимальная высота каждой вкладки (увеличено)
                  fontWeight: 500,            // Обычная толщина шрифта
                  textTransform: 'none',      // Не преобразует текст в заглавные буквы
                  fontSize: '0.925rem',       // Размер шрифта (14.8px)
                  alignItems: 'flex-start',   // Выравнивание содержимого по левому краю
                  justifyContent: 'flex-start', // Выравнивание по верхнему краю
                  pl: 3,                      // Отступ слева (24px)
                  pr: 4,                     // Отступ справа (32px)
                  '&.Mui-selected': {         // Стили для активной (выбранной) вкладки
                    fontWeight: 700,          // Жирный шрифт для активной вкладки
                    backgroundColor: 'background.paper', // Белый фон
                    borderRight: '4px solid',            // Синяя полоска справа (4px, увеличено)
                    borderRightColor: 'primary.main',    // Цвет полоски - основной цвет темы
                  },
                  '&:hover': {                // Стили при наведении курсора
                    backgroundColor: 'action.hover', // Светло-серый фон
                  },
                },
              }}
            >
              {filterGroups.map((group, index) => (
                <Tab
                  key={group.id}
                  label={group.label}
                  id={`filter-tab-${index}`}
                  aria-controls={`filter-tabpanel-${index}`}
                />
              ))}
            </Tabs>
          </Box>

          {/* 
            Правая колонка с содержимым фильтров - занимает всё оставшееся место
            - flex: 1 - растягивается на всю оставшуюся ширину
            - display: 'flex', flexDirection: 'column' - вертикальное расположение содержимого
            - overflow: 'hidden' - скрывает переполнение
          */}
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Панель "Доходность" (index 0) - фильтры по доходности облигаций */}
            <TabPanel value={activeTab} index={0}>
              {/* 
                Контейнер с прокруткой для содержимого панели
                - height: '100%' - занимает всю доступную высоту
                - overflowY: 'auto' - вертикальная прокрутка при переполнении
                - overflowX: 'hidden' - скрывает горизонтальную прокрутку
                - p: 3 - внутренние отступы (24px со всех сторон)
              */}
              <Box sx={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', p: 3 }}>
                {/* Вертикальный стек с отступами между элементами (spacing={4} = 32px) */}
                <Stack spacing={4} sx={{ width: '100%' }}>
                {/* Блок фильтра: Доходность купона относительно номинала */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Доходность купона относительно номинала
                  </Typography>
                  <CouponRangeFilter />
                </Box>
                <Divider />  {/* Разделительная линия между фильтрами */}
                {/* Блок фильтра: Доходность к погашению */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Доходность к погашению
                  </Typography>
                  <YieldRangeFilter />
                </Box>
                <Divider />
                {/* Блок фильтра: Доходность купона к текущей цене */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Доходность купона к текущей цене
                  </Typography>
                  <CouponYieldRangeFilter />
                </Box>
              </Stack>
              </Box>
            </TabPanel>

            {/* Панель "Даты" (index 1) - фильтры по датам погашения */}
            <TabPanel value={activeTab} index={1}>
              <Box sx={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', p: 3 }}>
                <Stack spacing={4} sx={{ width: '100%' }}>
                {/* Блок фильтра: Дата погашения облигации */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Дата погашения
                  </Typography>
                  <MaturityDateFilter />
                </Box>
              </Stack>
              </Box>
            </TabPanel>

            {/* 
              Панель "Категории" (index 2) - фильтры по типам, валютам, уровням листинга.
              Опции заданы на фронте; на бэкенд уходят только выбранные значения.
            */}
            <TabPanel value={activeTab} index={2}>
              <Box sx={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', p: 3 }}>
                <Stack spacing={4} sx={{ width: '100%' }}>
                {/* Блок фильтра: Уровень листинга на бирже (1, 2, 3 и т.д.) */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Уровень листинга
                  </Typography>
                  <ListLevelFilter />
                </Box>
                <Divider />
                {/* Блок фильтра: Валюта номинала облигации (RUB, USD, EUR и т.д.) */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Валюта
                  </Typography>
                  <CurrencyFilter />
                </Box>
                <Divider />
                {/* Блок фильтра: Тип облигации (ОФЗ, корпоративная, муниципальная и т.д.) */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Тип облигации
                  </Typography>
                  <BondTypeFilter />
                </Box>
                <Divider />
                {/* Блок фильтра: Вид облигации (фикс, флоатер, амортизируемая и т.д.) */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Вид облигации
                  </Typography>
                  <BondType43Filter />
                </Box>
              </Stack>
              </Box>
            </TabPanel>

            {/* Панель "Рейтинг" (index 3) - фильтры по рейтингам облигаций */}
            <TabPanel value={activeTab} index={3}>
              <Box sx={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', p: 3 }}>
                <Stack spacing={4} sx={{ width: '100%' }}>
                {/* Блок фильтра: Рейтинг облигации (AAA, AA+, AA, A и т.д.) */}
                <Box sx={{ width: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                    Рейтинг
                  </Typography>
                  <RatingRangeFilter />
                </Box>
              </Stack>
              </Box>
            </TabPanel>
          </Box>
        </Box>
      </DialogContent>

      {/* Нижняя панель с кнопками действий */}
      {/* 
        Параметры DialogActions:
        - p: 3 - внутренние отступы (24px)
        - gap: 2 - расстояние между элементами (16px)
        - borderTop - разделительная линия сверху
      */}
      <DialogActions
        sx={{
          p: 3,                      // Внутренние отступы со всех сторон
          gap: 2,                    // Расстояние между кнопками
          borderTop: '1px solid',    // Разделительная линия сверху
          borderColor: 'divider',    // Цвет разделителя
        }}
      >
        {/* Кнопка "Сбросить" - сбрасывает все фильтры к значениям по умолчанию */}
        <Button
          onClick={handleReset}
          startIcon={<ClearIcon />}  // Иконка крестика слева от текста
          variant="outlined"          // Контурный стиль кнопки
          color="secondary"           // Вторичный цвет темы
          sx={{ borderRadius: '12px' }} // Скругление углов
        >
          Сбросить
        </Button>
        {/* Растягивающийся элемент для выравнивания кнопок справа */}
        <Box sx={{ flexGrow: 1 }} />
        {/* Кнопка "Отмена" - закрывает модальное окно без применения фильтров */}
        <Button
          onClick={handleCancel}
          variant="outlined"          // Контурный стиль
          sx={{ borderRadius: '12px' }}
        >
          Отмена
        </Button>
        {/* Кнопка "Применить" - применяет фильтры и закрывает модальное окно */}
        <Button
          onClick={handleApply}
          variant="contained"         // Заполненный стиль (основная кнопка)
          color="primary"             // Основной цвет темы
          sx={{
            borderRadius: '12px',     // Скругление углов
            minWidth: '180px',        // Минимальная ширина кнопки
            py: 1.5,                  // Вертикальные отступы (12px)
            fontWeight: 600,          // Жирный шрифт
            fontSize: '1rem',         // Размер шрифта (16px)
          }}
        >
          Применить
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FiltersModal;
