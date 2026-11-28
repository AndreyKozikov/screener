import { Box } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

interface BlogArticleBodyProps {
  markdown: string;
  cover?: string | null;
}

export function BlogArticleBody({ markdown, cover }: BlogArticleBodyProps) {
  const coverUrl = cover ? URL.parse(cover, document.baseURI)?.href : undefined;
  return (
    <Box sx={{
      maxWidth: '100%',
      fontSize: '1.125rem',
      lineHeight: 1.7,
      overflowWrap: 'break-word',
      textWrap: 'pretty',
      '& > :first-child': { mt: 0 },
      '& > :last-child': { mb: 0 },
      '& p': { my: 1.5 },
      '& h2, & h3, & h4': { lineHeight: 1.3, mt: 3.5, mb: 1.5, fontWeight: 600, textWrap: 'balance', overflowWrap: 'break-word' },
      '& h2': { fontSize: '1.5rem' },
      '& h3': { fontSize: '1.25rem' },
      '& h4': { fontSize: '1.125rem' },
      '& img': { display: 'block', maxWidth: '100%', height: 'auto', borderRadius: 1.5, my: 2 },
      '& pre': {
        maxWidth: '100%',
        overflowX: 'auto',
        bgcolor: '#0f1b2d',
        color: '#eef4ff',
        p: 2,
        borderRadius: 1.5,
        fontSize: '0.875rem',
        lineHeight: 1.6,
      },
      '& code': { bgcolor: 'rgba(21,36,61,0.07)', px: 0.5, py: 0.25, borderRadius: 0.75, fontSize: '0.9em' },
      '& pre code': { bgcolor: 'transparent', p: 0, color: 'inherit', fontSize: 'inherit' },
      '& table': { display: 'block', width: '100%', maxWidth: '100%', overflowX: 'auto', borderCollapse: 'collapse', my: 2 },
      '& td, & th': { p: 1, px: 1.5, border: '1px solid', borderColor: 'divider', textAlign: 'left' },
      '& th': { bgcolor: 'grey.100', fontWeight: 600 },
      '& a': { color: 'primary.dark' },
      '& blockquote': {
        m: 0,
        my: 2,
        p: 2,
        bgcolor: 'grey.50',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1.5,
        color: 'text.secondary',
      },
      '& ul, & ol': { pl: 3, my: 1.5 },
      '& li + li': { mt: 0.5 },
      '& hr': { my: 3, border: 0, borderTop: '1px solid', borderColor: 'divider' },
    }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{ h1: 'h2' }}
        allowElement={(element) => {
          if (!coverUrl || element.tagName !== 'img') return true;
          const src = element.properties.src;
          return typeof src !== 'string' || URL.parse(src, document.baseURI)?.href !== coverUrl;
        }}
      >
        {markdown}
      </ReactMarkdown>
    </Box>
  );
}
