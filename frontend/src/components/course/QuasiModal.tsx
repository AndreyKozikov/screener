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
  Paper,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Интерфейс пропсов для компонента QuasiModal
 */
export interface QuasiModalProps {
  /** Флаг открытия/закрытия модального окна */
  open: boolean;
  /** Функция обработки закрытия модального окна */
  onClose: () => void;
}

/**
 * Контент описания квазисуверенных эмитентов
 */
const QUASI_CONTENT = `🏛️ **Квазисуверенные эмитенты: Что это такое?**

Квазисуверенные эмитенты (или заемщики) — это категория компаний или организаций, которые выпускают облигации или другие долговые инструменты, но не являются напрямую государством. Однако они имеют тесную связь с правительством: это могут быть государственные или полугосударственные агентства, корпорации с значительным участием государства или банки, где предполагается прямая или косвенная поддержка от правительства.

## 🔑 Ключевая особенность

Их ключевой особенностью является **низкий кредитный риск**, близкий к риску суверенного (государственного) долга, потому что государство часто гарантирует возврат средств — явно (через официальные гарантии) или implicitly (через ожидание помощи в случае проблем). Это делает их облигации более надежными по сравнению с чисто корпоративными, но менее надежными, чем прямые государственные облигации (например, ОФЗ в России).

## 📋 Примеры квазисуверенных эмитентов в России

* **Государственные корпорации** вроде "Роснефти", "Газпрома" или "РЖД" — они частично или полностью контролируются государством.
* **Банки с госучастием**, такие как Сбербанк или ВТБ.
* **Региональные или муниципальные органы**, если их долг поддерживается федеральным бюджетом.

## 💡 Привлекательность для инвесторов

В инвестициях такие эмитенты привлекательны для **консервативных инвесторов**, так как предлагают доходность выше, чем у суверенных облигаций, но с относительно низким риском дефолта благодаря "государственной подушке". 

⚠️ **Важно:** Всегда проверяйте уровень гарантий в проспекте эмиссии, чтобы избежать сюрпризов.`;

/**
 * Компонент модального окна для отображения информации о квазисуверенных эмитентах
 * 
 * @param props - Пропсы компонента
 * @returns React-компонент модального окна
 */
export const QuasiModal: React.FC<QuasiModalProps> = ({
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
          bgcolor: 'rgba(25, 118, 210, 0.05)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <AccountBalanceIcon sx={{ fontSize: 28, color: 'primary.main' }} />
          <Typography variant="h5" component="span" fontWeight={700}>
            Квазисуверенные эмитенты
          </Typography>
        </Box>
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
            {QUASI_CONTENT}
          </ReactMarkdown>

          {/* Дополнительная информационная карточка */}
          <Paper
            elevation={0}
            sx={{
              mt: 3,
              p: 2.5,
              bgcolor: 'rgba(25, 118, 210, 0.08)',
              borderLeft: 4,
              borderColor: 'primary.main',
              borderRadius: 1,
            }}
          >
            <Typography variant="subtitle2" fontWeight={600} gutterBottom sx={{ color: 'primary.dark' }}>
              💡 Практический совет
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
              При анализе квазисуверенных эмитентов обращайте внимание на долю государства в капитале, наличие официальных гарантий и стратегическую важность компании для экономики страны. Это поможет оценить реальную вероятность государственной поддержки в случае финансовых трудностей.
            </Typography>
          </Paper>
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



