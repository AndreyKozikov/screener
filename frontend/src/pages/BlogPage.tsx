import { useEffect, useState } from 'react';
import { Alert, Box, Button, CardActionArea, Chip, CircularProgress, Paper, Typography } from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { fetchPublishedArticle, fetchPublishedArticles, type BlogArticle } from '../api/blog';
import { BlogArticleBody } from '../components/blog/BlogArticleBody';

const panel = {
  borderRadius: 3,
  border: '1px solid rgba(255,255,255,0.82)',
  bgcolor: 'rgba(255,255,255,0.86)',
  boxShadow: '0 8px 24px rgba(73,105,160,0.1)',
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

  useEffect(() => {
    let active = true;
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
  }, [slug]);

  return (
    <Box sx={{ width: '100%', maxWidth: slug ? 900 : 1200, mx: 'auto', px: { xs: 2, md: 4 }, pb: 4, color: '#15243d' }}>
      {slug ? (
        <Button startIcon={<ArrowBackRoundedIcon />} onClick={() => onSelect(null)} sx={{ mb: 2 }}>
          Все статьи
        </Button>
      ) : (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h1">Блог</Typography>
          <Typography color="text.secondary">Практические материалы по облигациям, ставкам и портфельным решениям</Typography>
        </Box>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Box sx={{ textAlign: 'center', py: 4 }}><CircularProgress aria-label="Загрузка статей" /></Box>}
      {article && (
        <Paper component="article" sx={{ ...panel, overflow: 'hidden' }}>
          {article.cover_image_url && (
            <Box component="img" src={article.cover_image_url} alt={article.title}
              sx={{ display: 'block', width: '100%', maxHeight: '55vh', objectFit: 'contain' }} />
          )}
          <Box sx={{ p: { xs: 2.5, md: 5 }, overflowWrap: 'anywhere' }}>
            {article.category && <Chip label={article.category} size="small" color="primary" variant="outlined" />}
            <Typography variant="h1" sx={{ my: 2 }}>{article.title}</Typography>
            {article.summary && <Typography color="text.secondary" sx={{ mb: 3 }}>{article.summary}</Typography>}
            <BlogArticleBody markdown={article.content_markdown} cover={article.cover_image_url} />
          </Box>
        </Paper>
      )}
      {!slug && !loading && !error && (articles.length ? (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2,minmax(0,1fr))', lg: 'repeat(3,minmax(0,1fr))' }, gap: 2 }}>
          {articles.map((item) => (
            <Paper key={item.id} sx={{ ...panel, overflow: 'hidden' }}>
              <CardActionArea onClick={() => onSelect(item.slug)} sx={{ height: '100%', display: 'block', alignContent: 'start', p: 3, overflowWrap: 'anywhere' }}>
                {item.category && <Chip component="span" label={item.category} size="small" color="primary" variant="outlined" />}
                <Typography variant="h2" component="span" sx={{ display: 'block', mt: 1.5 }}>{item.title}</Typography>
                {item.summary && <Typography component="span" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{item.summary}</Typography>}
              </CardActionArea>
            </Paper>
          ))}
        </Box>
      ) : (
        <Paper sx={{ ...panel, p: 3 }}>Пока опубликованных статей нет.</Paper>
      ))}
    </Box>
  );
}

export default BlogPage;
