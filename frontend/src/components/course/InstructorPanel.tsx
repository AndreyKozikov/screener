import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import SchoolIcon from '@mui/icons-material/School';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import TipsAndUpdatesRoundedIcon from '@mui/icons-material/TipsAndUpdatesRounded';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface InstructorPanelProps {
  instruction: string;
  warning?: string;
  tip?: string;
}

const processMarkdownForModals = (text: string): string =>
  text.replace(/\[([^\]]+)\]\(modal:([^)]+)\)/g, (_match, linkText, modalType) =>
    `<span class="modal-link" data-modal-type="${modalType}" style="color: rgb(25, 118, 210); text-decoration: underline; cursor: pointer;">${linkText}</span>`,
  );

export const InstructorPanel: React.FC<InstructorPanelProps> = ({ instruction, warning, tip }) => {
  const renderMarkdown = (text: string, color: string) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={{
        p: ({ children }) => (
          <Typography variant="body2" component="p" sx={{ mb: 0.65, lineHeight: 1.5, color }}>
            {children}
          </Typography>
        ),
        strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
        em: ({ children }) => <em>{children}</em>,
        ul: ({ children }) => <Box component="ul" sx={{ pl: 2.5, mb: 0.75, color }}>{children}</Box>,
        ol: ({ children }) => <Box component="ol" sx={{ pl: 2.5, mb: 0.75, color }}>{children}</Box>,
        li: ({ children }) => (
          <Typography variant="body2" component="li" sx={{ mb: 0.35, lineHeight: 1.5, color }}>
            {children}
          </Typography>
        ),
        code: ({ children }) => (
          <Box component="code" sx={{ bgcolor: 'rgba(35,75,130,0.08)', px: 0.5, py: 0.2, borderRadius: 0.5, fontFamily: 'monospace', fontSize: '0.9em' }}>
            {children}
          </Box>
        ),
      }}
    >
      {processMarkdownForModals(text)}
    </ReactMarkdown>
  );

  const baseCardSx = {
    p: { xs: 1, sm: 1.5 },
    borderRadius: { xs: 2, sm: 2.5 },
    backdropFilter: 'blur(12px) saturate(135%)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.88)',
  };

  return (
    <Box component="section" aria-label="Инструкция, предупреждения и советы" sx={{ display: 'flex', flexDirection: 'column', gap: { xs: 0.8, sm: 1.1 }, mb: 1.5 }}>
      <Paper
        elevation={0}
        sx={{ ...baseCardSx, border: '1px solid rgba(58,131,245,0.22)', borderLeft: '3px solid #1976d2', bgcolor: 'rgba(227,240,255,0.62)' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: { xs: 0.8, sm: 1.25 } }}>
          <Box sx={{ width: { xs: 28, sm: 36 }, height: { xs: 28, sm: 36 }, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: { xs: '8px', sm: '10px' }, color: '#fff', bgcolor: '#1474e8', boxShadow: '0 4px 10px rgba(20,116,232,0.2)' }}>
            <SchoolIcon sx={{ fontSize: { xs: 17, sm: 21 } }} />
          </Box>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="subtitle2" fontWeight={750} sx={{ mb: 0.45, color: '#1559ad', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>
              Инструктор
            </Typography>
            {renderMarkdown(instruction, '#385274')}
          </Box>
        </Box>
      </Paper>

      {warning && (
        <Paper
          elevation={0}
          sx={{ ...baseCardSx, border: '1px solid rgba(255,157,43,0.24)', bgcolor: 'rgba(255,246,230,0.78)' }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: { xs: 0.8, sm: 1.25 } }}>
            <Box sx={{ width: { xs: 28, sm: 36 }, height: { xs: 28, sm: 36 }, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: { xs: '8px', sm: '10px' }, color: '#fff', bgcolor: '#ff9418', boxShadow: '0 4px 10px rgba(242,138,24,0.2)' }}>
              <WarningAmberRoundedIcon sx={{ fontSize: { xs: 17, sm: 21 } }} />
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="subtitle2" fontWeight={750} sx={{ mb: 0.45, color: '#a95a00', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>
                Важно
              </Typography>
              {renderMarkdown(warning, '#5c4a32')}
            </Box>
          </Box>
        </Paper>
      )}

      {tip && (
        <Paper
          elevation={0}
          sx={{ ...baseCardSx, border: '1px solid rgba(112,89,220,0.2)', bgcolor: 'rgba(242,238,255,0.78)' }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: { xs: 0.8, sm: 1.25 } }}>
            <Box sx={{ width: { xs: 28, sm: 36 }, height: { xs: 28, sm: 36 }, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: { xs: '8px', sm: '10px' }, color: '#fff', bgcolor: '#8065ed', boxShadow: '0 4px 10px rgba(112,89,220,0.2)' }}>
              <TipsAndUpdatesRoundedIcon sx={{ fontSize: { xs: 17, sm: 21 } }} />
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="subtitle2" fontWeight={750} sx={{ mb: 0.45, color: '#6049bf', fontSize: { xs: '0.72rem', sm: '0.82rem' } }}>
                Совет
              </Typography>
              {renderMarkdown(tip, '#4d4770')}
            </Box>
          </Box>
        </Paper>
      )}
    </Box>
  );
};
