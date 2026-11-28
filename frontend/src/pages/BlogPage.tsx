import { useEffect, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Link, Paper, Typography } from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { fetchPublishedArticle, fetchPublishedArticles, type BlogArticle } from '../api/blog';
import { BlogArticleBody } from '../components/blog/BlogArticleBody';
import { extractMarkdownImageUrls, stripMarkdownImages } from '../utils/blogMarkdown';

const panel = {
  borderRadius: 2,
  border: '1px solid rgba(255,255,255,0.82)',
  bgcolor: 'rgba(255,255,255,0.86)',
  boxShadow: '0 8px 24px rgba(73,105,160,0.1)',
};

const srOnly = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  p: 0,
  m: '-1px',
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

interface BlogPageProps {
  slug: string | null;
  onSelect: (slug: string | null) => void;
}

export function BlogPage({ slug, onSelect }: BlogPageProps) {
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [article, setArticle] = useState<BlogArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [coverFailed, setCoverFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    async function load() {
      try {
        if (slug) {
          const result = await fetchPublishedArticle(slug);
          if (active) setArticle(result);
        } else {
          const result = await fetchPublishedArticles();
          if (active) setArticles(result);
        }
      } catch {
        if (active) setError(slug ? 'Не удалось открыть статью.' : 'Не удалось загрузить статьи.');
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [slug, reloadKey]);

  useEffect(() => {
    setCoverFailed(false);
  }, [article?.id]);

  const displayTitle = article ? stripMarkdownImages(article.title) || article.slug : '';
  const displaySummary = article ? stripMarkdownImages(article.summary) : '';
  const coverFromTitle = article ? extractMarkdownImageUrls(article.title)[0] : undefined;
  const cover = article?.cover_image_url || coverFromTitle;
  const showCover = Boolean(cover) && !coverFailed;

  return (
    <Box sx={{
      width: '100%',
      maxWidth: slug
        ? { xs: '100%', sm: '48rem', md: '60rem', lg: '72rem', xl: '75rem' }
        : '85rem',
      mx: 'auto',
      px: { xs: 2, md: 3 },
      pb: { xs: 4, md: 6 },
      color: '#15243d',
    }}>
      {slug ? (
        <Button startIcon={<ArrowBackRoundedIcon />} onClick={() => onSelect(null)} sx={{ mb: 2, minHeight: 44 }}>
          Все статьи
        </Button>
      ) : (
        <Box sx={{ mb: 3 }}>
          <Typography
            variant="h1"
            sx={{ mb: 0.5, fontSize: 'clamp(2rem, 1.4rem + 1.6vw, 2.5rem)', lineHeight: 1.2, textWrap: 'balance' }}
          >
            Блог
          </Typography>
          <Typography color="text.secondary" sx={{ maxWidth: '60ch', fontSize: '1.0625rem' }}>
            Практические материалы по облигациям, ставкам и портфельным решениям
          </Typography>
        </Box>
      )}
      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2, alignItems: 'center' }}
          action={<Button color="inherit" size="small" onClick={() => setReloadKey((value) => value + 1)}>Повторить</Button>}
        >
          {error}
        </Alert>
      )}
      {loading && (
        <Box role="status" aria-live="polite" sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress aria-label="Загрузка статей" />
          <Box component="span" sx={srOnly}>Загрузка статей…</Box>
        </Box>
      )}
      {article && (
        <Paper component="article" sx={{ ...panel, overflow: 'hidden' }}>
          {showCover && cover && (
            <Box sx={{
              width: '100%',
              aspectRatio: { xs: '4 / 3', sm: '16 / 9', lg: '21 / 9' },
              bgcolor: 'grey.100',
              overflow: 'hidden',
            }}>
              <Box
                component="img"
                src={cover}
                alt=""
                onError={() => setCoverFailed(true)}
                sx={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </Box>
          )}
          <Box sx={{ p: { xs: 2.5, md: 4 }, overflowWrap: 'break-word' }}>
            <Box sx={{ maxWidth: '42rem', mx: 'auto' }}>
              {displayTitle && (
                <Typography
                  variant="h1"
                  component="h1"
                  sx={{
                    mb: 0.5,
                    fontSize: 'clamp(1.75rem, 1.3rem + 1.4vw, 2.5rem)',
                    lineHeight: 1.2,
                    textWrap: 'balance',
                    overflowWrap: 'break-word',
                  }}
                >
                  {displayTitle}
                </Typography>
              )}
              {article.category && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                  {article.category}
                </Typography>
              )}
              {displaySummary && (
                <Typography color="text.secondary" sx={{ mb: 3, fontSize: '1.125rem', lineHeight: 1.6 }}>
                  {displaySummary}
                </Typography>
              )}
              <BlogArticleBody markdown={article.content_markdown} cover={cover} />
            </Box>
          </Box>
        </Paper>
      )}
      {!slug && !loading && !error && (articles.length ? (
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'repeat(2,minmax(0,1fr))', lg: 'repeat(3,minmax(0,1fr))' },
          gap: 3,
        }}>
          {articles.map((item) => {
            const listTitle = stripMarkdownImages(item.title) || item.slug;
            const listSummary = stripMarkdownImages(item.summary);
            return (
              <Paper
                key={item.id}
                sx={{
                  ...panel,
                  position: 'relative',
                  display: 'flex',
                  overflow: 'hidden',
                  transition: 'box-shadow 180ms ease',
                  '&:focus-within': { boxShadow: '0 12px 30px rgba(73,105,160,0.16)' },
                  '@media (hover: hover) and (pointer: fine)': {
                    '&:hover': { boxShadow: '0 12px 30px rgba(73,105,160,0.16)' },
                  },
                }}
              >
                <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 1, width: '100%', overflowWrap: 'break-word' }}>
                  <Typography
                    variant="h2"
                    component="h2"
                    sx={{
                      fontSize: { xs: '1.25rem', md: '1.375rem' },
                      lineHeight: 1.3,
                      textWrap: 'balance',
                      overflowWrap: 'break-word',
                    }}
                  >
                    <Link
                      component="button"
                      type="button"
                      onClick={() => onSelect(item.slug)}
                      underline="hover"
                      color="inherit"
                      sx={{
                        display: 'block',
                        textAlign: 'left',
                        font: 'inherit',
                        p: 0,
                        border: 0,
                        bgcolor: 'transparent',
                        cursor: 'pointer',
                        '&::after': { content: '""', position: 'absolute', inset: 0, zIndex: 1 },
                        '&:focus-visible': {
                          outline: '2px solid',
                          outlineColor: 'primary.main',
                          outlineOffset: 4,
                          borderRadius: 0.5,
                        },
                      }}
                    >
                      <Box
                        component="span"
                        sx={{
                          display: '-webkit-box',
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {listTitle}
                      </Box>
                    </Link>
                  </Typography>
                  {listSummary && (
                    <Typography
                      color="text.secondary"
                      sx={{
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        lineHeight: 1.55,
                      }}
                    >
                      {listSummary}
                    </Typography>
                  )}
                  {item.category && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 'auto', pt: 0.5 }}>
                      {item.category}
                    </Typography>
                  )}
                </Box>
              </Paper>
            );
          })}
        </Box>
      ) : (
        <Paper sx={{ ...panel, p: 3 }}>Пока опубликованных статей нет.</Paper>
      ))}
    </Box>
  );
}

export default BlogPage;
