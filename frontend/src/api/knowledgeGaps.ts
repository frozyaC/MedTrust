import { GapStatus, KnowledgeGap } from '../types/knowledgeGaps';

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

/** Смена статуса пробела: `PATCH /api/v1/knowledge-gaps/{id}`. */
export async function updateGapStatus(
  gapId: string,
  status: GapStatus,
  options?: { note?: string },
): Promise<void> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps/${gapId}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ status, note: options?.note }),
  });

  if (!response.ok) {
    throw new Error(`Не удалось изменить статус: ${response.status}`);
  }
}

/**
 * Комментарий владельца БЗ. В таблице `knowledge_gaps` под него нет колонки,
 * поэтому сейчас он живёт только в состоянии страницы и не сохраняется на сервере.
 */
export async function saveGapComment(_gapId: string, _comment: string): Promise<void> {
  return;
}
