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


/** Участник группы похожих пробелов (ответ GET /knowledge-gap-groups). */
export interface GapGroupMember {
  gapId: number;
  question: string;
  status: GapStatus;
  occurrenceCount: number;
  firstSeenAt: string;
  lastSeenAt: string;
  similarity: number;
  assignmentSource: 'candidate' | 'owner_confirmed';
  removedAt?: string | null;
}

/** Группа похожих пробелов (ответ GET /knowledge-gap-groups). */
export interface GapGroup {
  id: number;
  title: string;
  representativeQuery: string;
  status: 'candidate' | 'open' | 'in_review' | 'resolved' | 'dismissed';
  activeMemberCount: number;
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string | null;
  confirmedBy?: string | null;
  confirmedAt?: string | null;
  members: GapGroupMember[];
}

/**
 * Группы, в которых участвует пробел: `GET /api/v1/knowledge-gap-groups?gap_id=`.
 */
export async function fetchGapGroups(gapId: string | number): Promise<GapGroup[]> {
  const response = await fetch(
    `${apiBaseUrl()}/api/v1/knowledge-gap-groups?gap_id=${encodeURIComponent(String(gapId))}`,
    { headers: JSON_HEADERS },
  );

  if (!response.ok) {
    throw new Error(`Не удалось загрузить группы пробелов: ${response.status}`);
  }

  return (await response.json()) as GapGroup[];
}

/**
 * Подтверждение группы-кандидата: `POST /api/v1/knowledge-gap-groups/{id}/confirm`.
 */
export async function confirmGapGroup(
  groupId: number,
  memberIds: number[],
  author?: string,
): Promise<GapGroup> {
  const response = await fetch(
    `${apiBaseUrl()}/api/v1/knowledge-gap-groups/${groupId}/confirm`,
    {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({
        member_ids: memberIds,
        ...(author ? { author } : {}),
      }),
    },
  );

  if (!response.ok) {
    let detail = `Не удалось подтвердить группу: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') detail = payload.detail;
    } catch {
      // keep status message
    }
    throw new Error(detail);
  }

  return (await response.json()) as GapGroup;
}

/**
 * Закрытие выбранных участников группы: `POST /api/v1/knowledge-gap-groups/{id}/resolve`.
 */
export async function resolveGapGroup(
  groupId: number,
  memberIds: number[],
  note: string,
  author?: string,
  idempotencyKey?: string,
): Promise<{ status: string; resolved_count: number; resolved_gap_ids: number[] }> {
  const response = await fetch(
    `${apiBaseUrl()}/api/v1/knowledge-gap-groups/${groupId}/resolve`,
    {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({
        member_ids: memberIds,
        note,
        ...(author ? { author } : {}),
        idempotency_key: idempotencyKey ?? crypto.randomUUID(),
      }),
    },
  );

  if (!response.ok) {
    let detail = `Не удалось закрыть группу: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') detail = payload.detail;
    } catch {
      // keep status message
    }
    throw new Error(detail);
  }

  return (await response.json()) as {
    status: string;
    resolved_count: number;
    resolved_gap_ids: number[];
  };
}