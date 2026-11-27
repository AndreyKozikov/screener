import { useEffect, useState } from 'react';
import { Alert, Box, Button, CardActionArea, Chip, CircularProgress, Paper, Typography } from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { fetchPublishedArticle, fetchPublishedArticles, type BlogArticle } from '../api/blog';
import { BlogArticleBody } from '../components/blog/BlogArticleBody';
import { extractMarkdownImageUrls, stripMarkdownImages } from '../utils/blogMarkdown';

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
  const [coverFailed, setCoverFailed] = useState(false);

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

  useEffect(() => {
    setCoverFailed(false);
  }, [article?.id]);

  const displayTitle = article ? stripMarkdownImages(article.title) : '';
  const displaySummary = article ? stripMarkdownImages(article.summary) : '';
  const coverFromTitle = article ? extractMarkdownImageUrls(article.title)[0] : undefined;
  const cover = article?.cover_image_url || coverFromTitle;
  const showCover = Boolean(cover) && !coverFailed;

  return (
    <Box sx={{ width: '100%', maxWidth: slug ? 1200 : 1280, mx: 'auto', px: { xs: 2, md: 3 }, pb: 4, color: '#15243d' }}>
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
          {showCover && cover && (
            <Box component="img" src={cover} alt={displayTitle}
              onError={() => setCoverFailed(true)}
              sx={{ display: 'block', width: '100%', maxHeight: '55vh', objectFit: 'contain' }} />
          )}
          <Box sx={{ p: { xs: 2.5, md: 4 }, overflowWrap: 'anywhere' }}>
            {article.category && <Chip label={article.category} size="small" color="primary" variant="outlined" />}
            {displayTitle && <Typography variant="h1" sx={{ my: 2 }}>{displayTitle}</Typography>}
            {displaySummary && <Typography color="text.secondary" sx={{ mb: 3 }}>{displaySummary}</Typography>}
            <BlogArticleBody markdown={article.content_markdown} cover={cover} />
          </Box>
        </Paper>
      )}
      {!slug && !loading && !error && (articles.length ? (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2,minmax(0,1fr))', lg: 'repeat(3,minmax(0,1fr))' }, gap: 2 }}>
          {articles.map((item) => {
            const listTitle = stripMarkdownImages(item.title) || item.slug;
            const listSummary = stripMarkdownImages(item.summary);
            return (
              <Paper key={item.id} sx={{ ...panel, overflow: 'hidden' }}>
                <CardActionArea onClick={() => onSelect(item.slug)} sx={{ height: '100%', display: 'block', alignContent: 'start', p: 3, overflowWrap: 'anywhere' }}>
                  {item.category && <Chip component="span" label={item.category} size="small" color="primary" variant="outlined" />}
                  <Typography variant="h2" component="span" sx={{ display: 'block', mt: 1.5 }}>{listTitle}</Typography>
                  {listSummary && <Typography component="span" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{listSummary}</Typography>}
                </CardActionArea>
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
