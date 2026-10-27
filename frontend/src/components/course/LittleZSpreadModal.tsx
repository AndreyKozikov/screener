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
 * Интерфейс пропсов для компонента LittleZSpreadModal
 */
export interface LittleZSpreadModalProps {
  /** Флаг открытия/закрытия модального окна */
  open: boolean;
  /** Функция обработки закрытия модального окна */
  onClose: () => void;
}

/**
 * Контент описания слишком маленького Z-спреда
 */
const LITTLE_Z_SPREAD_CONTENT = `🎯 **Что значит «Слишком маленький Z-спред»**

Z-spread (Зет-спред) — это ваша чистая компенсация за принятие кредитного риска и риска ликвидности, очищенная от всех особенностей купонов. Чем выше кредитный риск компании (т.е. чем ниже её кредитный рейтинг и хуже финансовое положение), тем больший Z-spread она обязана предложить, чтобы привлечь инвесторов.

Когда мы говорим, что Z-spread слишком маленький, это означает, что премия, которую вы получаете, не соответствует принятому вами риску.

**Неадекватная компенсация:** Вы принимаете на себя значительный кредитный риск, но дополнительная доходность (Z-spread) минимальна. По сути, вы даёте деньги рискованной компании почти по той же ставке, что и государству.

**Переоцененная бумага:** Облигация, вероятно, торгуется дорого. Инвесторы готовы покупать её по высокой цене, тем самым искусственно занижая её доходность и, соответственно, Z-spread.

**Риск-награда не сбалансированы:** В такой ситуации выгоднее выбрать безрисковый инструмент (например, ОФЗ) или облигацию с более низким риском, но с сопоставимым спредом, поскольку награда за риск в данной бумаге слишком низка.

## 📝 Практический Пример с Z-спредом
Давайте сравним две гипотетические облигации с одинаковой дюрацией (3 года) относительно безрисковой кривой RUONIA:

| Параметр | Облигация А (Крупный, надежный Банк, Рейтинг AAA) | Облигация Б (Небольшая, рискованная компания, Рейтинг BB) |
|----------|---------------------------------------------------|-----------------------------------------------------------|
| Кредитный риск | Минимальный | Высокий |
| Z-спред к кривой RUONIA | 1.0 п.п. (100 базисных пунктов) | 0.5 п.п. (50 базисных пунктов) |
| Интерпретация | Спред адекватный. За минимальный риск вы получаете премию в 1.0%. | Спред слишком маленький. За высокий риск (BB) вы получаете премию всего 0.5%. |

**Вывод:** В этом примере облигация Б, несмотря на высокий риск (рейтинг BB), предлагает вам меньшую премию, чем почти безрисковый Банк (рейтинг AAA). Z-спред в 0.5 п.п. не соответствует высокому кредитному риску. Вывод: от облигации Б стоит отказаться, поскольку она переоценена рынком, а награда за риск (0.5 п.п.) слишком мала.

## 🛠️ Как использовать Z-спред

**Сравнение с аналогами по рейтингу:** Это основной способ. Сравните Z-спред вашей облигации со средним Z-спредом по всем другим облигациям с таким же кредитным рейтингом.

**Оценка относительной стоимости:**

* Если облигация имеет рейтинг А, и её Z-спред составляет 2 п.п., но средний Z-спред для всех бумаг с рейтингом А равен 3 п.п., то ваша облигация, скорее всего, дорогая (недооплачивает риск), и её лучше не покупать.

* Если же Z-спред вашей облигации составляет 4 п.п. (при среднем 3 п.п. для этого рейтинга), она считается дешевой (переплачивает за риск) — это идеальный кандидат для покупки.

Таким образом, Z-спред — это ваш главный, наиболее точный инструмент для оценки относительной стоимости и справедливости награды за риск.`;

/**
 * Компонент модального окна для отображения информации о слишком маленьком спреде
 * 
 * @param props - Пропсы компонента
 * @returns React-компонент модального окна
 */
export const LittleZSpreadModal: React.FC<LittleZSpreadModalProps> = ({
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
          Слишком маленький Z-спред
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
            {LITTLE_Z_SPREAD_CONTENT}
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



