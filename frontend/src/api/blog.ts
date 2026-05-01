import { apiClient } from './client';

export type BlogArticleStatus = 'draft' | 'published';

export interface BlogArticle {
  id: number;
  slug: string;
  title: string;
  summary: string;
  content_markdown: string;
  category: string;
  cover_image_url: string | null;
  status: BlogArticleStatus;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface BlogArticlePayload {
  slug: string;
  title: string;
  summary: string;
  content_markdown: string;
  category: string;
  cover_image_url?: string | null;
  status: BlogArticleStatus;
}

export const fetchPublishedArticles = async (category?: string): Promise<BlogArticle[]> => {
  const response = await apiClient.get<BlogArticle[]>('/blog/articles', {
    params: category ? { category } : undefined,
  });
  return response.data;
};

export const fetchPublishedArticle = async (slug: string): Promise<BlogArticle> => {
  const response = await apiClient.get<BlogArticle>(`/blog/articles/${slug}`);
  return response.data;
};

export const fetchAdminArticles = async (): Promise<BlogArticle[]> => {
  const response = await apiClient.get<BlogArticle[]>('/blog-admin/articles');
  return response.data;
};

export const createArticle = async (payload: BlogArticlePayload): Promise<BlogArticle> => {
  const response = await apiClient.post<BlogArticle>('/blog-admin/articles', payload);
  return response.data;
};

export const updateArticle = async (
  articleId: number,
  payload: BlogArticlePayload,
): Promise<BlogArticle> => {
  const response = await apiClient.put<BlogArticle>(`/blog-admin/articles/${articleId}`, payload);
  return response.data;
};

export const deleteArticle = async (articleId: number): Promise<void> => {
  await apiClient.delete(`/blog-admin/articles/${articleId}`);
};

export const uploadBlogImage = async (file: File): Promise<{ url: string; filename: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<{ url: string; filename: string }>(
    '/blog-admin/uploads',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000,
    },
  );
  return response.data;
};
