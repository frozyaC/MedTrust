import { GapPeriod } from '../types/knowledgeGaps';

export const DAY_MS = 24 * 60 * 60 * 1000;

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

const DAY_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: 'short',
});

const TIME_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
});

export function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

export function endOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(23, 59, 59, 999);
  return copy;
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return DATE_TIME_FORMATTER.format(date);
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return TIME_FORMATTER.format(date);
}

export function formatDayLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';

  const today = startOfDay(new Date()).getTime();
  const day = startOfDay(date).getTime();
  const diffDays = Math.round((today - day) / DAY_MS);

  if (diffDays === 0) return 'сегодня';
  if (diffDays === 1) return 'вчера';
  return DAY_FORMATTER.format(date);
}

export function pluralRu(value: number, forms: [string, string, string]): string {
  const absolute = Math.abs(Math.trunc(value)) % 100;
  const last = absolute % 10;
  if (absolute > 10 && absolute < 20) return forms[2];
  if (last > 1 && last < 5) return forms[1];
  if (last === 1) return forms[0];
  return forms[2];
}

/** "3,2 дня" for the average resolution metric. */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '—';

  const days = ms / DAY_MS;
  if (days >= 1) {
    const value = days.toLocaleString('ru-RU', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
    return `${value} ${pluralRu(days, ['день', 'дня', 'дней'])}`;
  }

  const HOUR_MS = 60 * 60 * 1000;
  if (ms < HOUR_MS) {
    const minutes = Math.max(1, Math.round(ms / 60_000));
    return `${minutes} ${pluralRu(minutes, ['минута', 'минуты', 'минут'])}`;
  }

  const hours = Math.round(ms / HOUR_MS);
  return `${hours} ${pluralRu(hours, ['час', 'часа', 'часов'])}`;
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function parseDateInput(value: string, end = false): number | null {
  if (!value) return null;
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return null;
  const date = new Date(year, month - 1, day, end ? 23 : 0, end ? 59 : 0, end ? 59 : 0, end ? 999 : 0);
  const time = date.getTime();
  return Number.isNaN(time) ? null : time;
}

export function getPeriodRange(
  period: GapPeriod,
  customFrom: string,
  customTo: string,
): { start: number; end: number } {
  const now = Date.now();

  if (period === 'today') {
    return { start: startOfDay(new Date()).getTime(), end: now };
  }
  if (period === '7d') {
    return { start: now - 7 * DAY_MS, end: now };
  }
  if (period === '30d') {
    return { start: now - 30 * DAY_MS, end: now };
  }

  const start = parseDateInput(customFrom);
  const end = parseDateInput(customTo, true);
  if (start === null || end === null) {
    return { start: now - 7 * DAY_MS, end: now };
  }
  return start <= end ? { start, end } : { start: end, end: start };
}

export function periodLabel(period: GapPeriod): string {
  switch (period) {
    case 'today':
      return 'за сегодня';
    case '7d':
      return 'за 7 дней';
    case '30d':
      return 'за 30 дней';
    default:
      return 'за период';
  }
}

export function normalizeSearch(value: string): string {
  return value.trim().toLowerCase().replace(/ё/g, 'е');
}

export function matchesSearch(gap: { rawQuestion: string; resolvedQuery: string }, query: string): boolean {
  const normalized = normalizeSearch(query);
  if (!normalized) return true;
  return `${gap.rawQuestion} ${gap.resolvedQuery}`.toLowerCase().replace(/ё/g, 'е').includes(normalized);
}

export async function copyText(value: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Fall through to the legacy path for non-secure contexts.
  }

  try {
    const area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.top = '0';
    area.style.left = '0';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.focus();
    area.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(area);
    return copied;
  } catch {
    return false;
  }
}
