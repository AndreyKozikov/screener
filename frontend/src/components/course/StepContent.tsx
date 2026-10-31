import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Collapse,
  Chip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CalculateRoundedIcon from '@mui/icons-material/CalculateRounded';
import TipsAndUpdatesRoundedIcon from '@mui/icons-material/TipsAndUpdatesRounded';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PlaylistAddCheckRoundedIcon from '@mui/icons-material/PlaylistAddCheckRounded';
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
  stepCount: number;
  title: string;
  description: string;
  instruction: string;
  warning?: string;
  tip?: string;
  whatToDo: string;
  methodology?: string;
  practicalApplication?: string;
  onStepComplete: () => void;
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
  stepCount,
  title,
  description,
  instruction,
  warning,
  tip,
  whatToDo,
  methodology,
  practicalApplication,
  onStepComplete,
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
      <Typography variant={variant} component="p" sx={{ mb: 0.8, color: '#435b7f', lineHeight: 1.5, fontSize: { xs: '0.68rem', sm: '0.875rem' } }}>
        {children}
      </Typography>
    ),
    strong: ({ children }: any) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
    em: ({ children }: any) => <em>{children}</em>,
    ul: ({ children }: any) => <Box component="ul" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
    ol: ({ children }: any) => <Box component="ol" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
    li: ({ children }: any) => (
      <Typography variant={variant} component="li" sx={{ mb: 0.45, color: '#435b7f', lineHeight: 1.5, fontSize: { xs: '0.68rem', sm: '0.875rem' } }}>
        {children}
      </Typography>
    ),
    h1: ({ children }: any) => (
      <Typography variant="h4" component="h1" sx={{ mb: 0.8, mt: 1.5, color: '#102653', fontSize: { xs: '1rem', sm: '1.35rem' }, lineHeight: 1.3 }}>
        {children}
      </Typography>
    ),
    h2: ({ children }: any) => (
      <Typography variant="h5" component="h2" sx={{ mb: 0.75, mt: 1.5, color: '#102653', fontSize: { xs: '0.9rem', sm: '1.2rem' }, lineHeight: 1.3 }}>
        {children}
      </Typography>
    ),
    h3: ({ children }: any) => (
      <Typography variant="h6" component="h3" sx={{ mb: 0.6, mt: 1.1, color: '#24436c', fontSize: { xs: '0.8rem', sm: '1rem' }, lineHeight: 1.35 }}>
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
      <Box sx={{ mb: 2.25 }}>
        <Chip
          label={`Шаг ${stepNumber} из ${stepCount}`}
          size="small"
          variant="outlined"
          sx={{ mb: 1.2, color: '#1769d2', borderColor: 'rgba(23,105,210,0.34)', bgcolor: 'rgba(255,255,255,0.56)', fontWeight: 700 }}
        />
        <Typography variant="h4" component="h2" gutterBottom fontWeight={700} sx={{ color: '#0c1d4a', fontSize: { xs: '1rem', sm: '1.5rem', md: '1.85rem' }, lineHeight: 1.3, letterSpacing: '0.005em' }}>
          {title}
        </Typography>
        <Box sx={{ mb: 1.5 }}>
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
      <Card
        variant="outlined"
        sx={{
          mb: 1.25,
          borderRadius: { xs: 2, sm: 2.5 },
          borderColor: 'rgba(93, 142, 211, 0.23)',
          bgcolor: 'rgba(238, 246, 255, 0.62)',
          backdropFilter: 'blur(12px)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.88)',
        }}
      >
        <CardContent sx={{ p: { xs: 1, sm: 1.75 }, '&:last-child': { pb: { xs: 1, sm: 1.75 } } }}>
          <Box sx={{ display: 'flex', gap: { xs: 0.8, sm: 1.25 }, alignItems: 'flex-start' }}>
            <Box sx={{ width: { xs: 28, sm: 34 }, height: { xs: 28, sm: 34 }, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: { xs: '8px', sm: '10px' }, color: '#fff', bgcolor: '#1769d2', boxShadow: '0 4px 10px rgba(23,105,210,0.2)' }}>
              <PlaylistAddCheckRoundedIcon sx={{ fontSize: { xs: 17, sm: 20 } }} />
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="subtitle2" gutterBottom fontWeight={750} sx={{ color: '#11234c', fontSize: { xs: '0.72rem', sm: '0.875rem' } }}>
                Что нужно сделать сейчас
              </Typography>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={markdownComponents('body2')}
              >
                {processMarkdownForModals(whatToDo)}
              </ReactMarkdown>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Step Complete Button */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', mb: 1.1 }}>
        <Button
          variant="contained"
          onClick={onStepComplete}
          endIcon={<ArrowForwardIcon />}
          sx={{
            borderRadius: 2,
            px: 2.25,
            py: 1,
            textTransform: 'none',
            fontWeight: 700,
            background: 'linear-gradient(100deg, #126ce0 0%, #0875f4 100%)',
            boxShadow: '0 7px 16px rgba(14,103,220,0.22)',
            '&:hover': { background: 'linear-gradient(100deg, #0b5fc8 0%, #0666da 100%)' },
          }}
        >
          Завершить шаг {stepNumber} и перейти дальше
        </Button>
      </Box>

      {/* Expandable Details */}
      {(methodology || practicalApplication) && (
        <Box sx={{ mt: { xs: 0.8, sm: 1.2 } }}>
          <Button
            variant="text"
            onClick={() => setShowDetails(!showDetails)}
            endIcon={showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            sx={{
              display: 'flex',
              ml: 'auto',
              mb: 1,
              px: { xs: 1, sm: 1.25 },
              py: { xs: 0.65, sm: 0.8 },
              border: '1px solid rgba(93,142,211,0.2)',
              borderRadius: 2,
              textTransform: 'none',
              fontWeight: 700,
              fontSize: { xs: '0.68rem', sm: '0.8rem' },
              color: '#1769d2',
              bgcolor: 'rgba(237,246,255,0.58)',
              '&:hover': { bgcolor: 'rgba(226,239,255,0.8)', borderColor: 'rgba(93,142,211,0.34)' },
            }}
          >
            {showDetails ? 'Скрыть детали методологии' : 'Развернуть детали методологии'}
          </Button>

          <Collapse in={showDetails} sx={{ overflowAnchor: 'none' }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: { xs: 0.9, sm: 1.25 }, overflowAnchor: 'none' }}>
              {methodology && (
                <Card variant="outlined" sx={{ borderRadius: { xs: 2, sm: 2.5 }, bgcolor: 'rgba(232,244,255,0.72)', borderColor: 'rgba(73,139,224,0.22)', backdropFilter: 'blur(14px)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.85)' }}>
                  <CardContent sx={{ p: { xs: 1.1, sm: 1.8 }, '&:last-child': { pb: { xs: 1.1, sm: 1.8 } } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.8 }}>
                      <Box sx={{ width: 28, height: 28, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: '8px', color: '#fff', bgcolor: '#2879df' }}>
                        <CalculateRoundedIcon sx={{ fontSize: 17 }} />
                      </Box>
                      <Typography variant="subtitle1" fontWeight={750} sx={{ color: '#1559ad', fontSize: { xs: '0.78rem', sm: '0.95rem' } }}>
                        Методология оценки
                      </Typography>
                    </Box>
                    <Box sx={{ minWidth: 0, overflowX: 'auto' }}>
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
                <Card variant="outlined" sx={{ borderRadius: { xs: 2, sm: 2.5 }, bgcolor: 'rgba(243,238,255,0.76)', borderColor: 'rgba(133,103,224,0.22)', backdropFilter: 'blur(14px)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.85)' }}>
                  <CardContent sx={{ p: { xs: 1.1, sm: 1.8 }, '&:last-child': { pb: { xs: 1.1, sm: 1.8 } } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.8 }}>
                      <Box sx={{ width: 28, height: 28, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: '8px', color: '#fff', bgcolor: '#8065ed' }}>
                        <TipsAndUpdatesRoundedIcon sx={{ fontSize: 17 }} />
                      </Box>
                      <Typography variant="subtitle1" fontWeight={750} sx={{ color: '#6049bf', fontSize: { xs: '0.78rem', sm: '0.95rem' } }}>
                        Практическое применение
                      </Typography>
                    </Box>
                    <Box sx={{ minWidth: 0, overflowX: 'auto' }}>
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



