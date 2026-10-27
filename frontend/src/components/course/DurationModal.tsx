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
 * Интерфейс пропсов для компонента DurationModal
 */
export interface DurationModalProps {
  /** Флаг открытия/закрытия модального окна */
  open: boolean;
  /** Функция обработки закрытия модального окна */
  onClose: () => void;
}

/**
 * Контент описания дюрации облигаций
 */
const DURATION_CONTENT = `🕰️ **Что такое Дюрация облигаций?**

Дюрация — это ключевое понятие на рынке облигаций, которое помогает инвестору оценить два важнейших параметра бумаги: срок окупаемости и процентный риск.

В самой простой формулировке, дюрация (измеряемая в годах) показывает, как быстро инвестор вернет вложенные средства обратно, учитывая не только финальное погашение номинала, но и все купонные платежи, полученные по пути. Чем быстрее инвестор получает купоны, тем меньше у облигации дюрация. Понимание дюрации критически важно, поскольку она напрямую связывает решения Центрального банка по ключевой ставке с ценой вашей облигации: чем длиннее дюрация, тем сильнее скачок цены при изменении ставки.

## 1. Дюрация Маколея (Macaulay Duration)
Дюрация Маколея — это временная метрика, которая является первоначальным и наиболее фундаментальным видом дюрации.

**Что это показывает:** Это средневзвешенный срок окупаемости инвестиций. Она рассчитывается как средний срок, за который все денежные потоки (купоны и номинал) облигации, приведенные к текущей стоимости, будут возвращены инвестору. Фактически, это реальный, средний срок, в течение которого ваши деньги «заморожены» в этой бумаге.

**Практический смысл:** Если облигация имеет срок до погашения 10 лет, но дюрация Маколея составляет всего 7 лет, это означает, что вы вернете свой первоначальный капитал (в текущих ценах) за 7 лет благодаря получению промежуточных купонных выплат. Чем выше купон, тем быстрее вы возвращаете деньги, и тем меньше будет дюрация Маколея по сравнению со сроком до погашения.

**Использование:** Эта метрика чаще используется для теоретических расчетов, а также для целей иммунизации — стратегии, когда инвестор пытается сбалансировать сроки своих активов и обязательств.

## 2. Модифицированная Дюрация (Modified Duration)
Модифицированная дюрация — это самая важная и наиболее часто используемая на практике метрика, когда речь идет о рыночных рисках. Она является прямым производным от дюрации Маколея.

**Что это показывает:** Это метрика чувствительности цены облигации к изменению процентных ставок (доходности). Она показывает, на сколько процентов изменится рыночная цена облигации при изменении доходности к погашению на 1 процентный пункт (п.п.).

**Практический смысл:** Это ваш главный инструмент для оценки процентного риска. Если модифицированная дюрация облигации равна 5 годам, и Центральный банк внезапно повышает ключевую ставку на 1 п.п., цена этой облигации, вероятно, упадет примерно на 5%. И наоборот, если ставка упадет, цена вырастет на 5%. Поэтому, если вы ожидаете роста ставок (ужесточение ДКП), вы должны выбирать облигации с низкой модифицированной дюрацией (короткие), чтобы минимизировать падение цены.

**Использование:** Модифицированная дюрация используется для активного управления портфелем облигаций, для прогнозирования потенциальных убытков или прибыли от рыночных движений и для сравнения процентного риска между разными выпусками облигаций.

## 3. Эффективная Дюрация (Effective Duration)
Эффективная дюрация используется для оценки бумаг, чьи денежные потоки (купоны или срок погашения) могут меняться под влиянием внешних факторов.

**Что это показывает:** Эта метрика применяется к облигациям со встроенными опционами, например, к облигациям с офертой (правом досрочного погашения по требованию эмитента) или к облигациям с плавающим купоном (купон привязан к ставке ЦБ или RUONIA). В этих случаях изменение процентной ставки может не просто изменить цену, но и спровоцировать эмитента или инвестора использовать опцион, что кардинально меняет будущие денежные потоки.

**Практический смысл:** Поскольку Модифицированная дюрация некорректно работает с такими сложными бумагами (она предполагает неизменные денежные потоки), Эффективная дюрация рассчитывается путём моделирования: как изменится цена, если ставка изменится, и как это повлияет на вероятность исполнения опциона (например, оферты).

**Использование:** Для начинающего инвестора эта метрика часто не требуется, но она необходима при работе с корпоративными облигациями со сложной структурой или, например, с ипотечными ценными бумагами. Для большинства государственных и классических корпоративных облигаций используется именно Модифицированная дюрация.`;

/**
 * Компонент модального окна для отображения информации о дюрации облигаций
 * 
 * @param props - Пропсы компонента
 * @returns React-компонент модального окна
 */
export const DurationModal: React.FC<DurationModalProps> = ({
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
          Дюрация облигаций
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
            {DURATION_CONTENT}
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



