import { WikiDocumentContent } from '../types';
import { QueryApiError } from './query';

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
}

/**
 * Полный Markdown-текст статьи из локальной БД.
 */
export async function fetchWikiContent(documentId: string): Promise<WikiDocumentContent> {
  let response: Response;
  try {
    response = await fetch(
      `${apiBaseUrl()}/api/v1/knowledge/${encodeURIComponent(documentId)}/content`,
    );
  } catch {
    throw new QueryApiError('Не удалось загрузить текст статьи');
  }

  if (!response.ok) {
    let detail = `Не удалось загрузить текст статьи: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') {
        detail = payload.detail;
      }
    } catch {
      // keep status message
    }
    throw new QueryApiError(detail, response.status);
  }

  return (await response.json()) as WikiDocumentContent;
}