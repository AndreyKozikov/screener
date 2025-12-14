import React from 'react';
import { Paper, Box, Typography, Avatar } from '@mui/material';
import SchoolIcon from '@mui/icons-material/School';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface InstructorPanelProps {
  instruction: string;
  warning?: string;
  tip?: string;
}

export const InstructorPanel: React.FC<InstructorPanelProps> = ({
  instruction,
  warning,
  tip,
}) => {
  return (
    <Paper
      elevation={3}
      sx={{
        p: 3,
        mb: 3,
        bgcolor: 'rgba(25, 118, 210, 0.1)',
        borderLeft: 4,
        borderColor: 'primary.main',
        borderRadius: 2,
      }}
    >
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Avatar
          sx={{
            bgcolor: 'primary.main',
            width: 48,
            height: 48,
          }}
        >
          <SchoolIcon />
        </Avatar>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom color="primary.dark">
            Инструктор
          </Typography>
          <Box sx={{ mb: warning || tip ? 2 : 0 }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <Typography variant="body1" component="p" sx={{ mb: 1, lineHeight: 1.7 }}>
                    {children}
                  </Typography>
                ),
                strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
                em: ({ children }) => <em>{children}</em>,
                ul: ({ children }) => <Box component="ul" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                ol: ({ children }) => <Box component="ol" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                li: ({ children }) => (
                  <Typography variant="body1" component="li" sx={{ mb: 0.5, lineHeight: 1.7 }}>
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
              {instruction}
            </ReactMarkdown>
          </Box>
          {warning && (
            <Box
              sx={{
                mt: 2,
                p: 1.5,
                bgcolor: 'rgba(237, 108, 2, 0.15)',
                borderRadius: 1,
                borderLeft: 3,
                borderColor: 'warning.main',
              }}
            >
              <Typography variant="body2" fontWeight={600} color="warning.dark" gutterBottom>
                ⚠️ Важно:
              </Typography>
              <Box>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => (
                      <Typography variant="body2" component="p" sx={{ mb: 1 }}>
                        {children}
                      </Typography>
                    ),
                    strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
                    em: ({ children }) => <em>{children}</em>,
                    ul: ({ children }) => <Box component="ul" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                    ol: ({ children }) => <Box component="ol" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                    li: ({ children }) => (
                      <Typography variant="body2" component="li" sx={{ mb: 0.5 }}>
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
                  {warning}
                </ReactMarkdown>
              </Box>
            </Box>
          )}
          {tip && (
            <Box
              sx={{
                mt: 2,
                p: 1.5,
                bgcolor: 'rgba(25, 118, 210, 0.1)',
                borderRadius: 1,
                borderLeft: 3,
                borderColor: 'info.main',
              }}
            >
              <Typography variant="body2" fontWeight={600} color="info.dark" gutterBottom>
                💡 Совет:
              </Typography>
              <Box>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => (
                      <Typography variant="body2" component="p" sx={{ mb: 1 }}>
                        {children}
                      </Typography>
                    ),
                    strong: ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>,
                    em: ({ children }) => <em>{children}</em>,
                    ul: ({ children }) => <Box component="ul" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                    ol: ({ children }) => <Box component="ol" sx={{ pl: 3, mb: 1 }}>{children}</Box>,
                    li: ({ children }) => (
                      <Typography variant="body2" component="li" sx={{ mb: 0.5 }}>
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
                  {tip}
                </ReactMarkdown>
              </Box>
            </Box>
          )}
        </Box>
      </Box>
    </Paper>
  );
};
