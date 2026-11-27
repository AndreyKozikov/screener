/**
 * Разбор markdown-картинок в полях статьи.
 *
 * Заголовок, краткое описание и URL обложки — обычный текст, поэтому
 * попавший туда markdown-синтаксис картинки показывался бы как есть.
 * Эти функции помогают перенести такие картинки в тело статьи.
 */

const MARKDOWN_IMAGE_RE = /!\[([^\]]*)\]\(([^)\s]+)\)/g;

/** Вернуть все markdown-картинки из строки в исходном виде. */
export function extractMarkdownImages(value: string): string[] {
  return Array.from(value.matchAll(MARKDOWN_IMAGE_RE), (match) => match[0]);
}

/** Вернуть URL всех markdown-картинок из строки. */
export function extractMarkdownImageUrls(value: string): string[] {
  return Array.from(value.matchAll(MARKDOWN_IMAGE_RE), (match) => match[2]);
}

/** Убрать markdown-картинки из обычного текста. */
export function stripMarkdownImages(value: string): string {
  return value.replace(MARKDOWN_IMAGE_RE, ' ').replace(/\s+/g, ' ').trim();
}

/** Добавить в начало markdown-текста картинки, которых в нём ещё нет. */
export function prependMissingImages(content: string, images: string[]): string {
  if (!images.length) {
    return content;
  }
  const existingUrls = new Set(extractMarkdownImageUrls(content));
  const missing = images.filter((image) => {
    const [url] = extractMarkdownImageUrls(image);
    return url ? !existingUrls.has(url) : false;
  });
  if (!missing.length) {
    return content;
  }
  const prefix = missing.join('\n\n');
  const trimmedContent = content.trim();
  return trimmedContent ? `${prefix}\n\n${trimmedContent}` : prefix;
}
