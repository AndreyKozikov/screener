import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Collapse,
  Paper,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { InstructorPanel } from './InstructorPanel';
import { SubordinatedBondsModal } from './SubordinatedBondsModal';
import { DurationModal } from './DurationModal';
import { CompareDotModal } from './CompareDotModal';
import { LittleZSpreadModal } from './LittleZSpreadModal';
import { RuoniaModal } from './RuoniaModal';
import { QuasiModal } from './QuasiModal';

interface StepContentProps {
  stepNumber: number;
  title: string;
  description: string;
  instruction: string;
  warning?: string;
  tip?: string;
  whatToDo: string;
  methodology?: string;
  practicalApplication?: string;
  onStepComplete: () => void;
  onStepBack?: () => void;
}

/**
 * Для добавления нового типа модального окна:
 * 1. Добавьте обработку в useEffect (handleModalLinkClick)
 * 2. Используйте разметку [текст](modal:тип-модалки) в markdown контенте
 * 
 * Пример использования в markdown:
 * - [субординированные облигации](modal:subordinated-bonds)
 * - [**субординированные** облигации](modal:subordinated-bonds) - с жирным текстом
 */

export const StepContent: React.FC<StepContentProps> = ({
  stepNumber,
  title,
  description,
  instruction,
  warning,
  tip,
  whatToDo,
  methodology,
  practicalApplication,
  onStepComplete,
  onStepBack,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [isSubordinatedBondsModalOpen, setIsSubordinatedBondsModalOpen] = useState(false);
  const [isDurationModalOpen, setIsDurationModalOpen] = useState(false);
  const [isCompareDotModalOpen, setIsCompareDotModalOpen] = useState(false);
  const [isLittleZSpreadModalOpen, setIsLittleZSpreadModalOpen] = useState(false);
  const [isRuoniaModalOpen, setIsRuoniaModalOpen] = useState(false);
  const [isQuasiModalOpen, setIsQuasiModalOpen] = useState(false);

  /**
   * Обработка markdown текста: заменяем ссылки с modal: на span с обработчиком клика
   * Это предотвращает создание <a> тегов ReactMarkdown
   */
  const processMarkdownForModals = useCallback((text: string): string => {
    // Заменяем [текст](modal:тип) на HTML span с data-атрибутом
    // ReactMarkdown обработает это как обычный HTML через rehype-raw
    return text.replace(/\[([^\]]+)\]\(modal:([^)]+)\)/g, (_match, linkText, modalType) => {
      // Сохраняем markdown форматирование в тексте (например, **жирный**)
      // Создаем span с data-атрибутом
      return `<span class="modal-link" data-modal-type="${modalType}" style="color: rgb(25, 118, 210); text-decoration: underline; cursor: pointer;">${linkText}</span>`;
    });
  }, []);

  /**
   * Обработка DOM после рендеринга: добавляем обработчики клика на span с data-modal-type
   */
  React.useEffect(() => {
    const handleModalLinkClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const modalLink = target.closest('.modal-link[data-modal-type]');
      
      if (modalLink) {
        e.preventDefault();
        e.stopPropagation();
        const modalType = modalLink.getAttribute('data-modal-type');
        if (modalType === 'subordinated-bonds') {
          setIsSubordinatedBondsModalOpen(true);
        } else if (modalType === 'duration') {
          setIsDurationModalOpen(true);
        } else if (modalType === 'comparedot') {
          setIsCompareDotModalOpen(true);
        } else if (modalType === 'littlezspread') {
          setIsLittleZSpreadModalOpen(true);
        } else if (modalType === 'ruonia') {
          setIsRuoniaModalOpen(true);
        } else if (modalType === 'quasi') {
          setIsQuasiModalOpen(true);
        }
      }
    };

    // Добавляем обработчик на весь документ
    document.addEventListener('click', handleModalLinkClick, true);

    return () => {
      document.removeEventListener('click', handleModalLinkClick, true);
    };
  }, []);
  
  const markdownComponents = (variant: 'body1' | 'body2' = 'body1') => ({
    p: ({ children }: any) => (
      <Typography variant={variant} color="text.secondary" component="p" sx={{ mb: 1 }}>
        {children}
      </Typography>
    ),
    strong: ({ children }: any) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
    em: ({ children }: any) => <em>{children}</em>,
    ul: ({ children }: any) => <Box component="ul" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
    ol: ({ children }: any) => <Box component="ol" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
    li: ({ children }: any) => (
      <Typography variant={variant} color="text.secondary" component="li" sx={{ mb: 0.5 }}>
        {children}
      </Typography>
    ),
    h1: ({ children }: any) => (
      <Typography variant="h4" component="h1" sx={{ mb: 1, mt: 2 }}>
        {children}
      </Typography>
    ),
    h2: ({ children }: any) => (
      <Typography variant="h5" component="h2" sx={{ mb: 1, mt: 2 }}>
        {children}
      </Typography>
    ),
    h3: ({ children }: any) => (
      <Typography variant="h6" component="h3" sx={{ mb: 1, mt: 1.5 }}>
        {children}
      </Typography>
    ),
    a: ({ href, children }: any) => (
      <Box
        component="a"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        sx={{
          color: 'primary.main',
          textDecoration: 'underline',
          '&:hover': {
            color: 'primary.dark',
          },
        }}
      >
        {children}
      </Box>
    ),
    code: ({ children }: any) => (
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
    table: ({ children }: any) => (
      <Box
        component="table"
        sx={{
          width: '100%',
          borderCollapse: 'collapse',
          mb: 2,
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
    thead: ({ children }: any) => (
      <Box component="thead" sx={{ bgcolor: 'action.hover' }}>
        {children}
      </Box>
    ),
    tbody: ({ children }: any) => (
      <Box component="tbody">{children}</Box>
    ),
    tr: ({ children }: any) => (
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
    th: ({ children }: any) => (
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
        <Typography variant={variant} component="span">
          {children}
        </Typography>
      </Box>
    ),
    td: ({ children }: any) => (
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
        <Typography variant={variant} component="span" color="text.secondary">
          {children}
        </Typography>
      </Box>
    ),
  });

  return (
    <Box sx={{ animation: 'fadeIn 0.3s ease-in' }}>
      {/* Step Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" component="h2" gutterBottom fontWeight={700}>
          Шаг {stepNumber}: {title}
        </Typography>
        <Box sx={{ mb: 2 }}>
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]} 
            rehypePlugins={[rehypeRaw]}
            components={markdownComponents('body1')}
          >
            {processMarkdownForModals(description)}
          </ReactMarkdown>
        </Box>
      </Box>

      {/* Instructor Panel */}
      <InstructorPanel instruction={instruction} warning={warning} tip={tip} />

      {/* What to Do Now */}
      <Card variant="outlined" sx={{ mb: 3, bgcolor: 'action.selected' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom fontWeight={600} color="primary">
            Что нужно сделать сейчас:
          </Typography>
          <Box>
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]} 
              rehypePlugins={[rehypeRaw]}
              components={markdownComponents('body1')}
            >
              {processMarkdownForModals(whatToDo)}
            </ReactMarkdown>
          </Box>
        </CardContent>
      </Card>

      {/* Step Complete Button */}
      <Paper
        elevation={3}
        sx={{
          p: 3,
          mb: 3,
          bgcolor: 'rgba(25, 118, 210, 0.1)',
          border: 2,
          borderColor: 'primary.main',
          borderRadius: 2,
        }}
      >
        <Typography variant="h6" gutterBottom color="primary.dark">
          Готовы перейти к следующему шагу?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Изучите материал этого шага и переходите к следующему, когда будете готовы.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {stepNumber > 1 && onStepBack && (
            <Button
              variant="outlined"
              color="primary"
              size="large"
              startIcon={<ArrowBackIcon />}
              onClick={onStepBack}
              sx={{ mt: 1 }}
            >
              Вернуться к предыдущему шагу
            </Button>
          )}
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={onStepComplete}
            sx={{ mt: 1 }}
          >
            Завершить шаг {stepNumber} и перейти дальше
          </Button>
        </Box>
      </Paper>

      {/* Expandable Details */}
      {(methodology || practicalApplication) && (
        <Box sx={{ mt: 3 }}>
          <Button
            fullWidth
            variant="outlined"
            onClick={() => setShowDetails(!showDetails)}
            endIcon={showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            sx={{ mb: 2 }}
          >
            {showDetails ? 'Скрыть детали' : 'Развернуть детали методологии'}
          </Button>

          <Collapse in={showDetails} sx={{ overflowAnchor: 'none' }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, overflowAnchor: 'none' }}>
              {methodology && (
                <Card variant="outlined" sx={{ bgcolor: 'rgba(46, 125, 50, 0.08)' }}>
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom color="success.dark">
                      Методология оценки
                    </Typography>
                    <Box>
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]} 
                        rehypePlugins={[rehypeRaw]}
                        components={markdownComponents('body1')}
                      >
                        {processMarkdownForModals(methodology)}
                      </ReactMarkdown>
                    </Box>
                  </CardContent>
                </Card>
              )}

              {practicalApplication && (
                <Card variant="outlined" sx={{ bgcolor: 'rgba(237, 108, 2, 0.08)' }}>
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight={600} gutterBottom color="warning.dark">
                      Практическое применение
                    </Typography>
                    <Box>
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]} 
                        rehypePlugins={[rehypeRaw]}
                        components={markdownComponents('body1')}
                      >
                        {processMarkdownForModals(practicalApplication)}
                      </ReactMarkdown>
                    </Box>
                  </CardContent>
                </Card>
              )}
            </Box>
          </Collapse>
        </Box>
      )}

      {/* Модальное окно с описанием субординированных облигаций */}
      <SubordinatedBondsModal
        open={isSubordinatedBondsModalOpen}
        onClose={() => setIsSubordinatedBondsModalOpen(false)}
      />

      {/* Модальное окно с описанием дюрации облигаций */}
      <DurationModal
        open={isDurationModalOpen}
        onClose={() => setIsDurationModalOpen(false)}
      />

      {/* Модальное окно с описанием точки сравнения */}
      <CompareDotModal
        open={isCompareDotModalOpen}
        onClose={() => setIsCompareDotModalOpen(false)}
      />

      {/* Модальное окно с описанием слишком маленького спреда */}
      <LittleZSpreadModal
        open={isLittleZSpreadModalOpen}
        onClose={() => setIsLittleZSpreadModalOpen(false)}
      />

      {/* Модальное окно с описанием кривой RUONIA */}
      <RuoniaModal
        open={isRuoniaModalOpen}
        onClose={() => setIsRuoniaModalOpen(false)}
      />

      {/* Модальное окно с описанием квазисуверенных эмитентов */}
      <QuasiModal
        open={isQuasiModalOpen}
        onClose={() => setIsQuasiModalOpen(false)}
      />
    </Box>
  );
};
