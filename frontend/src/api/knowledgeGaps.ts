import type {
  GapComment, GapStatus, KnowledgeGap, KnowledgeGapGroup, GapGroupStatus,
  GapGroupConfirmRequest, GapGroupDetachRequest, GapGroupResolveRequest, GapGroupResolveResult,
} from '../types/knowledgeGaps';

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
}

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export class GapApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'GapApiError';
  }
}

async function groupRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gap-groups${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: JSON_HEADERS,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg ?? 'Некорректные данные').join('; ')
      : `Не удалось выполнить запрос: ${response.status}`;
    throw new GapApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export function gapGroupErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : 'Не удалось выполнить запрос. Проверьте соединение.';
  return error instanceof GapApiError && error.status === 409
    ? `${message}. Обновите данные и проверьте состав группы.` : message;
}

export function fetchGapGroups(filters: { status?: GapGroupStatus; gap_id?: number; limit?: number } = {}): Promise<KnowledgeGapGroup[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.gap_id !== undefined) params.set('gap_id', String(filters.gap_id));
  params.set('limit', String(filters.limit ?? 500));
  return groupRequest(`?${params}`);
}

export function fetchGapGroup(groupId: number): Promise<KnowledgeGapGroup> {
  return groupRequest(`/${groupId}`);
}

export function confirmGapGroup(groupId: number, request: GapGroupConfirmRequest): Promise<KnowledgeGapGroup> {
  return groupRequest(`/${groupId}/confirm`, request);
}

export function detachGapGroupMember(groupId: number, gapId: number, request: GapGroupDetachRequest): Promise<KnowledgeGapGroup> {
  return groupRequest(`/${groupId}/members/${gapId}/detach`, request);
}

export function resolveGapGroup(groupId: number, request: GapGroupResolveRequest): Promise<GapGroupResolveResult> {
  return groupRequest(`/${groupId}/resolve`, request);
}

/**
 * Загрузка всех пробелов: `GET /api/v1/knowledge-gaps`.
 * Период, статус, источник, причина и поиск фильтруются на клиенте (см. KnowledgeGapsPage).
 */
export async function fetchKnowledgeGaps(gapId?: number): Promise<KnowledgeGap[]> {
  const query = gapId === undefined ? '' : `?gap_id=${gapId}`;
  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps${query}`, {
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
