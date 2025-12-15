import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Box,
  Typography,
  Fade,
  Backdrop,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Интерфейс пропсов для компонента RuoniaModal
 */
export interface RuoniaModalProps {
  /** Флаг открытия/закрытия модального окна */
  open: boolean;
  /** Функция обработки закрытия модального окна */
  onClose: () => void;
}

/**
 * Контент описания кривой RUONIA
 */
const RUONIA_CONTENT = `**Кривая RUONIA и Кривая Бескупонной Доходности (КБД)**

Как начинающий инвестор, вы уже знаете, что для оценки корпоративной облигации её нужно сравнить с безрисковым эталоном. В России такими эталонами являются Кривая RUONIA и Кривая Бескупонной Доходности (КБД). Обе они показывают, какой доходность должна быть при полном отсутствии кредитного риска, но они отражают разные сегменты рынка.

## 1. Кривая Бескупонной Доходности (КБД)
КБД — это самый чистый и фундаментальный эталон, построенный на основе государственных облигаций (ОФЗ).

**Что это такое:** КБД — это теоретический график, который показывает, какой должна быть доходность на каждый срок (например, 1 год, 3 года, 5 лет), если бы в экономике существовали идеальные безрисковые облигации без купонов. Она строится путём сложных математических расчётов (их называют бутстреппинг) на основе цен всех торгуемых ОФЗ, исключая влияние различных купонов.

**Что она показывает инвестору:** Она отражает долгосрочные ожидания рынка относительно движения ключевой ставки ЦБ и является лучшим показателем срочной структуры государственного долга. Если доходность на длинных сроках (КБД на 5 лет) выше, чем на коротких (КБД на 1 год), рынок ожидает сохранения или роста ставок в будущем.

**Где используется:** КБД является общепринятым эталоном для оценки долгосрочных облигаций и служит базой для расчёта различных финансовых показателей, связанных с государственным риском.

## 2. Кривая RUONIA (Ruble Overnight Index Average)
Кривая RUONIA строится на основе ставки денежного рынка и отражает стоимость денег в банковской системе.

**Что это такое:** RUONIA — это средняя процентная ставка, по которой крупнейшие российские банки кредитуют друг друга на условиях «овернайт» (то есть на один день). Кривая RUONIA – это график, который показывает, какой будет эта ставка, если прогнозировать ее на разные сроки (1 месяц, 3 месяца, 6 месяцев и т.д.).

**Что она показывает инвестору:** Она отражает текущую стоимость денег и краткосрочные ожидания банков по будущей динамике ключевой ставки ЦБ РФ. Так как ЦБ активно управляет ликвидностью, чтобы ставка RUONIA оставалась близка к Ключевой ставке, эта кривая является отличным индикатором краткосрочных процентных рисков.

**Где используется:** Кривая RUONIA часто используется как бенчмарк (ориентир) для облигаций с плавающим купоном (ОФЗ-ПК или корпоративные флоатеры), а главное — она является основой для расчета Z-spread (Зет-спреда), самого точного показателя премии за кредитный риск.

## 3. Чем они отличаются? (Сводная таблица)

| Характеристика | Кривая Бескупонной Доходности (КБД) | Кривая RUONIA |
|----------------|-------------------------------------|---------------|
| Базовый актив | Государственные облигации (ОФЗ) | Межбанковское кредитование (Ставка «овернайт») |
| Отражаемый риск | Долгосрочный государственный/суверенный риск | Краткосрочный риск ликвидности и денежного рынка |
| Основная цель | Оценка общей срочной структуры ставок. | Оценка стоимости фондирования. База для Z-spread. |
| Срок | Часто используется для всех сроков, включая длинные (5+ лет). | Чаще используется для краткосрочных и среднесрочных ставок. |

**Главное отличие для новичка:**

* **КБД** — это ваш глобальный компас для оценки, куда движутся ставки в долгосрочной перспективе, и идеальная база для сравнения длинных ОФЗ.

* **Кривая RUONIA** — это точный инструмент для определения справедливой премии (Z-spread) по корпоративным облигациям, так как она лучше отражает актуальную стоимость денег на рынке.

## 4. Влияние ставки RUONIA на облигации
Ставка RUONIA является одним из ключевых индикаторов стоимости денег в экономике, и её влияние на облигации с разными типами купона проявляется по-разному.

### 4.1. Облигации с постоянным (фиксированным) купоном

**Влияние на цену:** Ставка RUONIA косвенно влияет на цену облигаций с фиксированным купоном. Если ожидается, что RUONIA будет расти (что почти всегда означает ожидание роста Ключевой ставки ЦБ), это повышает рыночную доходность. В результате, инвесторы требуют более высокую доходность от всех облигаций, и цена старых облигаций с низким фиксированным купоном падает.

**Влияние на спред:** Как мы обсуждали, Кривая RUONIA используется как основа для расчёта Z-spread. Таким образом, для облигаций с фиксированным купоном RUONIA помогает оценить, насколько справедливо рынок оценивает кредитный риск эмитента.

### 4.2. Облигации с плавающим купоном (Флоатеры)

**Прямая привязка:** Для облигаций с плавающим купоном (флоатеров) влияние RUONIA прямое и непосредственное. Купон по таким бумагам часто привязан к ставке RUONIA или Ключевой ставке ЦБ, а иногда к ставке RUONIA с дополнительной премией.

**Защита от риска:** Если RUONIA растёт, растёт и размер купона по вашему флоатеру, что защищает вас от процентного риска. Поскольку купон меняется в соответствии с рынком, цена такой облигации остается относительно стабильной (её дюрация близка к нулю), что делает флоатеры привлекательными в периоды роста ставки ЦБ.`;

/**
 * Компонент модального окна для отображения информации о кривой RUONIA
 * 
 * @param props - Пропсы компонента
 * @returns React-компонент модального окна
 */
export const RuoniaModal: React.FC<RuoniaModalProps> = ({
  open,
  onClose,
}) => {
  /**
   * Восстановление прокрутки при закрытии модального окна
   * MUI Dialog сам управляет блокировкой прокрутки, но иногда нужно явно восстановить стили
   */
  useEffect(() => {
    if (!open) {
      // Убеждаемся, что прокрутка разблокирована после закрытия
      const timer = setTimeout(() => {
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
      }, 100);

      return () => clearTimeout(timer);
    }
  }, [open]);

  /**
   * Обработка нажатия клавиши Escape для закрытия модального окна
   */
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        onClose();
      }
    };

    if (open) {
      document.addEventListener('keydown', handleEscape);
      return () => {
        document.removeEventListener('keydown', handleEscape);
      };
    }
  }, [open, onClose]);

  /**
   * Обработка клика по backdrop (фону) для закрытия модального окна
   */
  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      fullScreen={false}
      TransitionComponent={Fade}
      TransitionProps={{ timeout: 300 }}
      BackdropComponent={Backdrop}
      BackdropProps={{
        timeout: 300,
        onClick: handleBackdropClick,
      }}
      disableScrollLock={false}
      PaperProps={{
        sx: {
          borderRadius: 2,
          maxHeight: '90vh',
          m: { xs: 2, sm: 3 },
        },
      }}
    >
      {/* Заголовок модального окна */}
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="h5" component="span" fontWeight={700}>
          Кривая RUONIA и КБД
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{
            ml: 2,
            '&:hover': {
              bgcolor: 'action.hover',
            },
          }}
          aria-label="Закрыть"
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      {/* Контент модального окна */}
      <DialogContent
        sx={{
          pt: 3,
          pb: 2,
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            bgcolor: 'action.hover',
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'action.disabled',
            borderRadius: '4px',
            '&:hover': {
              bgcolor: 'text.secondary',
            },
          },
        }}
      >
        <Box>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => (
                <Typography variant="body1" component="p" sx={{ mb: 2, lineHeight: 1.7 }}>
                  {children}
                </Typography>
              ),
              strong: ({ children }) => (
                <strong style={{ fontWeight: 700, color: 'inherit' }}>{children}</strong>
              ),
              em: ({ children }) => <em>{children}</em>,
              ul: ({ children }) => (
                <Box component="ul" sx={{ pl: 3, mb: 2, mt: 1 }}>
                  {children}
                </Box>
              ),
              ol: ({ children }) => (
                <Box component="ol" sx={{ pl: 3, mb: 2, mt: 1 }}>
                  {children}
                </Box>
              ),
              li: ({ children }) => (
                <Typography variant="body1" component="li" sx={{ mb: 1, lineHeight: 1.7 }}>
                  {children}
                </Typography>
              ),
              h1: ({ children }) => (
                <Typography variant="h4" component="h1" sx={{ mb: 2, mt: 3, fontWeight: 700 }}>
                  {children}
                </Typography>
              ),
              h2: ({ children }) => (
                <Typography variant="h5" component="h2" sx={{ mb: 1.5, mt: 2.5, fontWeight: 600 }}>
                  {children}
                </Typography>
              ),
              h3: ({ children }) => (
                <Typography variant="h6" component="h3" sx={{ mb: 1, mt: 2, fontWeight: 600 }}>
                  {children}
                </Typography>
              ),
              table: ({ children }) => (
                <Box
                  component="table"
                  sx={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    mb: 3,
                    mt: 2,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    overflow: 'hidden',
                  }}
                >
                  {children}
                </Box>
              ),
              thead: ({ children }) => (
                <Box component="thead" sx={{ bgcolor: 'action.hover' }}>
                  {children}
                </Box>
              ),
              tbody: ({ children }) => (
                <Box component="tbody">{children}</Box>
              ),
              tr: ({ children }) => (
                <Box
                  component="tr"
                  sx={{
                    borderBottom: 1,
                    borderColor: 'divider',
                    '&:last-child': {
                      borderBottom: 0,
                    },
                  }}
                >
                  {children}
                </Box>
              ),
              th: ({ children }) => (
                <Box
                  component="th"
                  sx={{
                    p: 1.5,
                    textAlign: 'left',
                    fontWeight: 600,
                    borderRight: 1,
                    borderColor: 'divider',
                    '&:last-child': {
                      borderRight: 0,
                    },
                  }}
                >
                  {children}
                </Box>
              ),
              td: ({ children }) => (
                <Box
                  component="td"
                  sx={{
                    p: 1.5,
                    borderRight: 1,
                    borderColor: 'divider',
                    '&:last-child': {
                      borderRight: 0,
                    },
                  }}
                >
                  {children}
                </Box>
              ),
              code: ({ children }) => (
                <Box
                  component="code"
                  sx={{
                    bgcolor: 'rgba(0, 0, 0, 0.08)',
                    px: 0.5,
                    py: 0.25,
                    borderRadius: 0.5,
                    fontFamily: 'monospace',
                    fontSize: '0.9em',
                  }}
                >
                  {children}
                </Box>
              ),
            }}
          >
            {RUONIA_CONTENT}
          </ReactMarkdown>
        </Box>
      </DialogContent>

      {/* Действия модального окна */}
      <DialogActions
        sx={{
          px: 3,
          pb: 2,
          pt: 2,
          borderTop: 1,
          borderColor: 'divider',
        }}
      >
        <Button
          onClick={onClose}
          variant="contained"
          color="primary"
          size="large"
          sx={{ minWidth: 120 }}
        >
          Понятно
        </Button>
      </DialogActions>
    </Dialog>
  );
};
