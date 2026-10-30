import { GapComment, GapStatus, KnowledgeGap } from '../types/knowledgeGaps';

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
}

const JSON_HEADERS = { 'Content-Type': 'application/json' };

/**
 * Загрузка всех пробелов: `GET /api/v1/knowledge-gaps`.
 * Период, статус, источник, причина и поиск фильтруются на клиенте (см. KnowledgeGapsPage).
 */
export async function fetchKnowledgeGaps(): Promise<KnowledgeGap[]> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps`, {
    headers: JSON_HEADERS,
  });

  if (!response.ok) {
    throw new Error(`Не удалось загрузить пробелы: ${response.status}`);
  }

  return (await response.json()) as KnowledgeGap[];
}

/**
 * Смена статуса пробела: `PATCH /api/v1/knowledge-gaps/{id}`.
 * Непустой `note` сервер сохраняет как комментарий от `author` и возвращает его.
 */
export async function updateGapStatus(
  gapId: string,
  status: GapStatus,
  options?: { note?: string; author?: string },
): Promise<GapComment | undefined> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps/${gapId}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ status, note: options?.note, author: options?.author }),
  });

  if (!response.ok) {
    throw new Error(`Не удалось изменить статус: ${response.status}`);
  }

  const data = (await response.json()) as { comment?: GapComment };
  return data.comment;
}

/** Комментарий владельца БЗ: `POST /api/v1/knowledge-gaps/{id}/comments`. */
export async function addGapComment(
  gapId: string,
  body: string,
  author: string,
): Promise<GapComment> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps/${gapId}/comments`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ body, author }),
  });

  if (!response.ok) {
    throw new Error(`Не удалось сохранить комментарий: ${response.status}`);
  }

  return (await response.json()) as GapComment;
}
