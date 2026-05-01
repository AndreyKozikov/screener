import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import UploadIcon from '@mui/icons-material/Upload';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

import {
  createArticle,
  deleteArticle,
  fetchAdminArticles,
  updateArticle,
  uploadBlogImage,
  type BlogArticle,
  type BlogArticlePayload,
  type BlogArticleStatus,
} from '../api/blog';

const emptyPayload: BlogArticlePayload = {
  slug: '',
  title: '',
  summary: '',
  content_markdown: '',
  category: 'Облигации',
  cover_image_url: '',
  status: 'draft',
};

const makeSlug = (value: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яё\s-]/gi, '')
    .replace(/[а-яё]/gi, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return slug || `article-${Date.now()}`;
};

export const BlogAdminPage: React.FC = () => {
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<BlogArticlePayload>(emptyPayload);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedArticle = useMemo(
    () => articles.find((article) => article.id === selectedId) ?? null,
    [articles, selectedId],
  );

  const loadArticles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setArticles(await fetchAdminArticles());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить статьи');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadArticles();
  }, []);

  const selectArticle = (article: BlogArticle) => {
    setSelectedId(article.id);
    setForm({
      slug: article.slug,
      title: article.title,
      summary: article.summary,
      content_markdown: article.content_markdown,
      category: article.category,
      cover_image_url: article.cover_image_url ?? '',
      status: article.status,
    });
    setMessage(null);
    setError(null);
  };

  const createNew = () => {
    setSelectedId(null);
    setForm(emptyPayload);
    setMessage(null);
    setError(null);
  };

  const saveArticle = async () => {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        ...form,
        slug: form.slug || makeSlug(form.title),
        cover_image_url: form.cover_image_url || null,
      };
      const saved = selectedArticle
        ? await updateArticle(selectedArticle.id, payload)
        : await createArticle(payload);
      setMessage('Статья сохранена');
      setSelectedId(saved.id);
      await loadArticles();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить статью');
    } finally {
      setIsSaving(false);
    }
  };

  const removeArticle = async () => {
    if (!selectedArticle) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await deleteArticle(selectedArticle.id);
      setMessage('Статья удалена');
      createNew();
      await loadArticles();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось удалить статью');
    } finally {
      setIsSaving(false);
    }
  };

  const uploadImage = async (file: File | null) => {
    if (!file) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const result = await uploadBlogImage(file);
      const imageMarkdown = `\n\n![${file.name}](${result.url})\n`;
      setForm((prev) => ({
        ...prev,
        cover_image_url: prev.cover_image_url || result.url,
        content_markdown: `${prev.content_markdown}${imageMarkdown}`,
      }));
      setMessage(`Изображение загружено: ${result.url}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить изображение');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#F8FAFC', p: { xs: 2, md: 3 } }}>
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" component="h1" fontWeight={700}>
          Управление блогом
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Скрытая страница публикации: доступна только прямым переходом на /blog-admin.
        </Typography>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '320px 1fr' }, gap: 3 }}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: 'fit-content' }}>
          <Button
            fullWidth
            variant="contained"
            startIcon={<AddIcon />}
            onClick={createNew}
            sx={{ mb: 2, textTransform: 'none' }}
          >
            Новая статья
          </Button>
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Stack spacing={1}>
              {articles.map((article) => (
                <Card
                  key={article.id}
                  variant={selectedId === article.id ? 'elevation' : 'outlined'}
                  onClick={() => selectArticle(article)}
                  sx={{ cursor: 'pointer' }}
                >
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Typography variant="subtitle2" fontWeight={700}>
                      {article.title}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 1 }}>
                      <Chip label={article.status} size="small" color={article.status === 'published' ? 'success' : 'default'} />
                      <Chip label={article.category} size="small" />
                    </Box>
                  </CardContent>
                </Card>
              ))}
              {articles.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  Статей пока нет.
                </Typography>
              )}
            </Stack>
          )}
        </Paper>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', xl: '1fr 1fr' }, gap: 3 }}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              {selectedArticle ? 'Редактирование статьи' : 'Новая статья'}
            </Typography>
            <Stack spacing={2}>
              <TextField
                label="Заголовок"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                fullWidth
              />
              <TextField
                label="Slug"
                value={form.slug}
                helperText="Латиница, цифры и дефисы. Можно оставить пустым при создании."
                onChange={(event) => setForm((prev) => ({ ...prev, slug: event.target.value }))}
                fullWidth
              />
              <TextField
                label="Краткое описание"
                value={form.summary}
                onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))}
                fullWidth
                multiline
                minRows={2}
              />
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 180px' }, gap: 2 }}>
                <TextField
                  label="Категория"
                  value={form.category}
                  onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
                  fullWidth
                />
                <TextField
                  select
                  label="Статус"
                  value={form.status}
                  onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as BlogArticleStatus }))}
                >
                  <MenuItem value="draft">draft</MenuItem>
                  <MenuItem value="published">published</MenuItem>
                </TextField>
              </Box>
              <TextField
                label="URL обложки"
                value={form.cover_image_url ?? ''}
                onChange={(event) => setForm((prev) => ({ ...prev, cover_image_url: event.target.value }))}
                fullWidth
              />
              <Button component="label" variant="outlined" startIcon={<UploadIcon />} sx={{ textTransform: 'none' }}>
                Загрузить картинку
                <input
                  hidden
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  onChange={(event) => void uploadImage(event.target.files?.[0] ?? null)}
                />
              </Button>
              <TextField
                label="Markdown"
                value={form.content_markdown}
                onChange={(event) => setForm((prev) => ({ ...prev, content_markdown: event.target.value }))}
                fullWidth
                multiline
                minRows={16}
              />
              <Divider />
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={saveArticle}
                  disabled={isSaving || !form.title.trim()}
                  sx={{ textTransform: 'none' }}
                >
                  Сохранить
                </Button>
                {selectedArticle && (
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={removeArticle}
                    disabled={isSaving}
                    sx={{ textTransform: 'none' }}
                  >
                    Удалить
                  </Button>
                )}
              </Box>
            </Stack>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Preview
            </Typography>
            <Box sx={{ '& img': { maxWidth: '100%', borderRadius: 1 } }}>
              <Typography variant="h4" component="h2" fontWeight={700} gutterBottom>
                {form.title || 'Заголовок статьи'}
              </Typography>
              {form.summary && (
                <Typography color="text.secondary" sx={{ mb: 2 }}>
                  {form.summary}
                </Typography>
              )}
              {form.cover_image_url && (
                <Box
                  component="img"
                  src={form.cover_image_url}
                  alt={form.title}
                  sx={{ width: '100%', maxHeight: 240, objectFit: 'cover', mb: 2 }}
                />
              )}
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {form.content_markdown || 'Начните писать Markdown...'}
              </ReactMarkdown>
            </Box>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
};

export default BlogAdminPage;
