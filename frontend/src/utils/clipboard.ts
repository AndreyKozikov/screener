/**
 * Копирование текста в буфер обмена с запасным вариантом для HTTP и старых браузеров.
 */
export const copyTextToClipboard = async (text: string): Promise<boolean> => {
  if (!text) return false;

  if (navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Если современный API запрещён политикой браузера, пробуем legacy-способ.
    }
  }

  try {
    const activeElement = document.activeElement as HTMLElement | null;
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.top = '-9999px';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    try {
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, text.length);
      return document.execCommand('copy');
    } finally {
      textarea.remove();
      activeElement?.focus();
    }
  } catch {
    return false;
  }
};
