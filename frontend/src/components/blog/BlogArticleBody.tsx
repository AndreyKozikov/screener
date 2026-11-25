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
      lineHeight: 1.7, overflowWrap: 'anywhere',
      '& > :first-child': { mt: 0 },
      '& > :last-child': { mb: 0 },
      '& h1, & h2, & h3': { lineHeight: 1.3, mt: 3 },
      '& img': { maxWidth: '100%', height: 'auto', borderRadius: 2 },
      '& pre, & table': { maxWidth: '100%', overflowX: 'auto' },
      '& table': { display: 'block', borderCollapse: 'collapse' },
      '& td, & th': { p: 1, border: 1, borderColor: 'divider' },
      '& a': { color: 'primary.dark' },
    }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}
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
