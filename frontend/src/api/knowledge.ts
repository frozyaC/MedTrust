import { apiBaseUrl, apiFetch } from './client';
import { WikiDocumentContent } from '../types';
import { QueryApiError } from './query';


/**
 * Полный Markdown-текст статьи из локальной БД.
 */
export async function fetchWikiContent(documentId: string): Promise<WikiDocumentContent> {
  let response: Response;
  try {
    response = await apiFetch(
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