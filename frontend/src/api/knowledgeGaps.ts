import { GapFilters, GapPeriod, GapSort, KnowledgeGap, GapStatus } from '../types/knowledgeGaps';
import { DEMO_GAPS } from '../data/knowledgeGaps';

/**
 * API для карты пробелов.
 *
 * Сейчас все методы возвращают моки из `data/knowledgeGaps.ts`.
 * Когда бэк будет готов (endpoints `GET /api/v1/knowledge-gaps`,
 * `PATCH /api/v1/knowledge-gaps/{id}`, `POST /api/v1/knowledge-gaps/{id}/comment`),
 * нужно будет заменить тела функций на реальные `fetch`-запросы.
 *
 * Интерфейс (`fetchKnowledgeGaps`, `updateGapStatus`, `saveGapComment`)
 * менять не нужно — только их реализацию.
 */

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
}

// Флаг демо-режима. Когда бэк будет готов — поставить false.
const USE_MOCKS = true;

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  // Когда появится реальная авторизация — добавить сюда:
  // const token = localStorage.getItem('medtrust.token');
  // if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function simulateDelay(ms = 420): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/**
 * Загрузка списка пробелов.
 *
 * Сейчас: возвращает моки (с имитацией задержки).
 * Потом: `GET /api/v1/knowledge-gaps?period=...&status=...&...`
 */
export async function fetchKnowledgeGaps(params: {
  period: GapPeriod;
  customFrom: string;
  customTo: string;
  filters: GapFilters;
  sort: GapSort;
}): Promise<KnowledgeGap[]> {
  if (USE_MOCKS) {
    await simulateDelay(550);
    // Возвращаем копию, чтобы не мутировать оригинал
    return DEMO_GAPS.map((gap) => ({ ...gap }));
  }

  const query = new URLSearchParams();
  query.set('period', params.period);
  if (params.period === 'custom') {
    query.set('from', params.customFrom);
    query.set('to', params.customTo);
  }
  query.set('sort', params.sort);
  if (params.filters.statuses.length > 0) {
    query.set('status', params.filters.statuses.join(','));
  }
  if (params.filters.sources.length > 0) {
    query.set('source', params.filters.sources.join(','));
  }
  if (params.filters.reasons.length > 0) {
    query.set('reason', params.filters.reasons.join(','));
  }
  if (params.filters.search.trim()) {
    query.set('search', params.filters.search.trim());
  }

  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps?${query}`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Не удалось загрузить пробелы: ${response.status}`);
  }

  return (await response.json()) as KnowledgeGap[];
}

/**
 * Смена статуса пробела.
 *
 * Сейчас: имитация задержки.
 * Потом: `PATCH /api/v1/knowledge-gaps/{id}` с телом `{ status, note }`.
 */
export async function updateGapStatus(
  gapId: string,
  status: GapStatus,
  options?: { note?: string },
): Promise<void> {
  if (USE_MOCKS) {
    await simulateDelay();
    return;
  }

  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps/${gapId}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ status, note: options?.note }),
  });

  if (!response.ok) {
    throw new Error(`Не удалось изменить статус: ${response.status}`);
  }
}

/**
 * Сохранение комментария владельца БЗ.
 *
 * Сейчас: имитация задержки.
 * Потом: `POST /api/v1/knowledge-gaps/{id}/comment` с телом `{ comment }`.
 */
export async function saveGapComment(gapId: string, comment: string): Promise<void> {
  if (USE_MOCKS) {
    await simulateDelay();
    return;
  }

  const response = await fetch(`${apiBaseUrl()}/api/v1/knowledge-gaps/${gapId}/comment`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ comment }),
  });

  if (!response.ok) {
    throw new Error(`Не удалось сохранить комментарий: ${response.status}`);
  }
}