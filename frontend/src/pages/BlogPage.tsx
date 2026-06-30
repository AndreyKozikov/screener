import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Paper,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SchoolIcon from '@mui/icons-material/School';
import ArticleIcon from '@mui/icons-material/Article';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

import { fetchPublishedArticle, fetchPublishedArticles, type BlogArticle } from '../api/blog';
import { BondSelectionGuidePage } from './BondSelectionGuidePage';

type BlogMode = 'list' | 'article' | 'guide';

export const BlogPage: React.FC = () => {
  const [mode, setMode] = useState<BlogMode>('list');
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<BlogArticle | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const categories = useMemo(
    () => Array.from(new Set(articles.map((article) => article.category))).filter(Boolean),
    [articles],
  );

  useEffect(() => {
    const loadArticles = async () => {
      setIsLoading(true);
      setError(null);
      try {
        setArticles(await fetchPublishedArticles());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить статьи');
      } finally {
        setIsLoading(false);
      }
    };
    void loadArticles();
  }, []);

  const openArticle = async (article: BlogArticle) => {
    setIsLoading(true);
    setError(null);
    try {
      setSelectedArticle(await fetchPublishedArticle(article.slug));
      setMode('article');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось открыть статью');
    } finally {
      setIsLoading(false);
    }
  };

  if (mode === 'guide') {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => setMode('list')}
          sx={{ mb: 2, textTransform: 'none' }}
        >
          Назад к блогу
        </Button>
        <BondSelectionGuidePage />
      </Box>
    );
  }

  if (mode === 'article' && selectedArticle) {
    return (
      <Box sx={{ width: '100%', maxWidth: 1040, mx: 'auto', px: 2, pb: 4 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => setMode('list')}
          sx={{ mb: 2, textTransform: 'none' }}
        >
          Назад к блогу
        </Button>
        <Paper elevation={2} sx={{ overflow: 'hidden', borderRadius: 2 }}>
          {selectedArticle.cover_image_url && (
            <CardMedia
              component="img"
              image={selectedArticle.cover_image_url}
              alt={selectedArticle.title}
              sx={{ width: '100%', height: 'auto' }}
            />
          )}
          <Box sx={{ p: { xs: 2, md: 4 } }}>
            <Chip label={selectedArticle.category} size="small" sx={{ mb: 2 }} />
            <Typography variant="h3" component="h1" fontWeight={700} gutterBottom>
              {selectedArticle.title}
            </Typography>
            {selectedArticle.summary && (
              <Typography variant="h6" color="text.secondary" sx={{ mb: 3 }}>
                {selectedArticle.summary}
              </Typography>
            )}
            <Box sx={{ '& img': { maxWidth: '100%', borderRadius: 1 } }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {(() => {
                  const content = selectedArticle.content_markdown;
                  const cover = selectedArticle.cover_image_url;
                  if (!cover) return content;
                  const escapedUrl = cover.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
                  const regex = new RegExp(`\\s*!\\[[^\\]]*\\]\\(${escapedUrl}\\)\\s*`, 'g');
                  return content.replace(regex, '\n\n').trim();
                })()}
              </ReactMarkdown>
            </Box>
          </Box>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', maxWidth: 1280, mx: 'auto', px: 2, pb: 4 }}>
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" component="h1" fontWeight={700}>
          Блог
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
          Практические материалы по облигациям, ставкам и портфельным решениям
        </Typography>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.1fr 1fr' }, gap: 3, mb: 3 }}>
        <Card
          onClick={() => setMode('guide')}
          sx={{
            cursor: 'pointer',
            borderRadius: 2,
            border: '1px solid #D7E3EA',
            bgcolor: 'background.paper',
          }}
        >
          <CardContent sx={{ p: 3 }}>
            <SchoolIcon color="primary" sx={{ fontSize: 44, mb: 1 }} />
            <Typography variant="h5" fontWeight={700} gutterBottom>
              Советы по выбору облигаций
            </Typography>
            <Typography color="text.secondary">
              Интерактивный пошаговый гид с методологией, практическими примерами и пояснениями терминов.
            </Typography>
          </CardContent>
        </Card>

        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} gutterBottom>
            Темы блога
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {categories.length > 0 ? (
              categories.map((category) => <Chip key={category} label={category} size="small" />)
            ) : (
              <Typography variant="body2" color="text.secondary">
                Категории появятся после публикации статей.
              </Typography>
            )}
          </Box>
        </Paper>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
        {articles.map((article) => (
          <Card
            key={article.id}
            onClick={() => openArticle(article)}
            sx={{
              borderRadius: 2,
              display: 'flex',
              flexDirection: 'column',
              cursor: 'pointer',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              '&:hover': {
                transform: 'translateY(-4px)',
                boxShadow: 4,
              },
            }}
          >
            {article.cover_image_url && (
              <CardMedia component="img" height="150" image={article.cover_image_url} alt={article.title} />
            )}
            <CardContent sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <ArticleIcon fontSize="small" color="primary" />
                <Chip label={article.category} size="small" />
              </Box>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                {article.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {article.summary || 'Без описания'}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>

      {!isLoading && articles.length === 0 && (
        <Paper variant="outlined" sx={{ p: 3, mt: 2, textAlign: 'center' }}>
          <Typography color="text.secondary">
            Пока опубликованных статей нет. Интерактивный гид уже доступен выше.
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default BlogPage;
