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
 * Интерфейс пропсов для компонента SubordinatedBondsModal
 */
export interface SubordinatedBondsModalProps {
  /** Флаг открытия/закрытия модального окна */
  open: boolean;
  /** Функция обработки закрытия модального окна */
  onClose: () => void;
}

/**
 * Контент описания субординированных облигаций
 */
const SUBORDINATED_BONDS_CONTENT = `🧐 **Субординированные облигации: Что это и почему они рискованнее?**

Субординированные облигации (или просто «суборды») — это особый и более рискованный вид долга, который обычно выпускают банки и финансовые организации. Они отличаются от обычных корпоративных облигаций (которые называют приоритетными или старшими), потому что ставят инвестора в очередь на выплаты после всех остальных кредиторов.

🏦 **В чём главное отличие?**

Чтобы понять, что такое субординированная облигация, представьте очередь к кассе, когда банкротство наступает (наихудший сценарий):

* **Первые в очереди (Приоритетные кредиторы):** Государство, вкладчики (с депозитами, защищёнными АСВ), владельцы обычных облигаций. Эти люди и организации получат свои деньги назад в первую очередь.
* **Последние в очереди (Субординированные кредиторы):** Владельцы субординированных облигаций.
* **Самые последние в очереди:** Акционеры.

Субординация (от лат. subordinatio — подчинение) означает, что требования по этим бумагам удовлетворяются только после того, как будут полностью удовлетворены все требования по обычным долгам (включая обычные облигации).

💡 **Плюсы и минусы для инвестора**

| Характеристика | Плюс (Выгода) | Минус (Риск) |
|----------------|---------------|--------------|
| **Доходность** | Предлагают более высокую доходность (процентную ставку), чем обычные облигации того же эмитента. Это ваша премия за риск. | |
| **Риск потери** | | В случае банкротства или финансового кризиса эмитента (например, банка) риск не получить назад свой капитал (или получить лишь часть) значительно выше, чем по обычным облигациям. |
| **Особые условия** | | Существуют специфические условия, которые могут привести к списанию долга или конвертации его в акции, если банкротство угрожает банку. |
| **Статус капитала** | Эти облигации часто засчитываются в капитал банка, что позволяет банку соблюдать требования регулятора. | Но для инвестора это означает дополнительный риск. |

⚠️ **Вывод для начинающего инвестора**

Субординированные облигации подходят для инвесторов с высокой толерантностью к риску, которые готовы к частичной или полной потере капитала ради повышенной доходности.

🛑 **Совет:** Если вы только начинаете инвестировать и главная цель — сохранение капитала и низкий риск, избегайте субординированных облигаций. Начните с менее рискованных инструментов, таких как ОФЗ или обычные облигации крупных, надёжных компаний.`;

/**
 * Компонент модального окна для отображения информации о субординированных облигациях
 * 
 * @param props - Пропсы компонента
 * @returns React-компонент модального окна
 */
export const SubordinatedBondsModal: React.FC<SubordinatedBondsModalProps> = ({
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
          Субординированные облигации
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
            {SUBORDINATED_BONDS_CONTENT}
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
