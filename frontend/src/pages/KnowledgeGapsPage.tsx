import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CalendarDays, ChevronRight, RefreshCw } from 'lucide-react';
import { AdminHeader } from '../components/admin/AdminHeader';
import { AdminSidebar } from '../components/admin/AdminSidebar';
import { ConfirmResolveModal } from '../components/admin/ConfirmResolveModal';
import { DeveloperGapsView } from '../components/admin/DeveloperGapsView';
import { DismissGapModal } from '../components/admin/DismissGapModal';
import { EmptyState } from '../components/admin/EmptyState';
import { GapDetailPanel } from '../components/admin/GapDetailPanel';
import { GapFilterBar } from '../components/admin/GapFilterBar';
import { GapTable, GapTableSkeleton } from '../components/admin/GapTable';
import type { RequestedGapStatus } from '../components/admin/GapTable';
import { MetricCard } from '../components/admin/MetricCard';
import { Toast } from '../components/Toast';
import {
  AdminRole,
  DismissReason,
  GapFilters,
  GapPeriod,
  GapSort,
  GapStatus,
  KnowledgeGap,
} from '../types/knowledgeGaps';
import {
  DEFAULT_FILTERS,
  DEMO_ADMIN_USER,
  DISMISS_REASON_OPTIONS,
  PERIOD_OPTIONS,
  STATUS_OPTIONS,
} from '../data/knowledgeGaps';
import {
  DAY_MS,
  formatDuration,
  getPeriodRange,
  periodLabel,
  toDateInputValue,
} from '../lib/format';

import { fetchKnowledgeGaps, updateGapStatus, addGapComment } from '../api/knowledgeGaps';

type PageState = 'loading' | 'ready' | 'error';

interface ToastState {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

interface StatusChangeOptions {
  note?: string;
}

function parsePeriod(value: string | null): GapPeriod {
  if (value === 'today' || value === '7d' || value === '30d' || value === 'custom') {
    return value;
  }
  return '7d';
}

function parseSort(value: string | null): GapSort {
  if (value === 'oldest' || value === 'longest') return value;
  return 'newest';
}

function parseStatusFilter(value: string | null): GapStatus[] {
  if (value === 'all') return STATUS_OPTIONS.map((option) => option.value);
  if (!value) return [...DEFAULT_FILTERS.statuses];

  const allowed = new Set<GapStatus>(STATUS_OPTIONS.map((option) => option.value));
  const parsed = value
    .split(',')
    .map((item) => item.trim())
    .filter((item): item is GapStatus => allowed.has(item as GapStatus));

  return parsed.length > 0 ? parsed : [...DEFAULT_FILTERS.statuses];
}

// function simulateSave(): Promise<void> {
//   return new Promise((resolve, reject) => {
//     window.setTimeout(() => {
//       if (typeof navigator !== 'undefined' && navigator.onLine === false) {
//         reject(new Error('offline'));
//         return;
//       }
//       resolve();
//     }, 420);
//   });
// }

interface PeriodSelectorProps {
  period: GapPeriod;
  onPeriodChange: (period: GapPeriod) => void;
  customFrom: string;
  customTo: string;
  onCustomFromChange: (value: string) => void;
  onCustomToChange: (value: string) => void;
}

function PeriodSelector({
  period,
  onPeriodChange,
  customFrom,
  customTo,
  onCustomFromChange,
  onCustomToChange,
}: PeriodSelectorProps) {
  return (
    <div className="flex shrink-0 flex-col items-start gap-1.5 xl:min-w-[430px] xl:items-end">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-med-text-muted">Период</span>
        <div className="inline-flex flex-wrap gap-1 rounded-lg border border-med-border bg-med-surface p-1 shadow-med-card">
          {PERIOD_OPTIONS.map((option) => {
            const active = option.value === period;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onPeriodChange(option.value)}
                aria-pressed={active}
                className={`inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors ${
                  active
                    ? 'bg-med-primary text-white shadow-sm'
                    : 'text-med-text-secondary hover:bg-med-bg hover:text-med-text-primary'
                }`}
              >
                {option.value === 'custom' && <CalendarDays className="h-3.5 w-3.5" />}
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {period === 'custom' && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-med-text-secondary">
            с
            <input
              type="date"
              value={customFrom}
              onChange={(event) => onCustomFromChange(event.target.value)}
              aria-label="Начало периода"
              className="h-9 rounded-lg border border-med-border bg-med-surface px-2 text-xs text-med-text-primary outline-none transition-colors focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
            />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-med-text-secondary">
            по
            <input
              type="date"
              value={customTo}
              onChange={(event) => onCustomToChange(event.target.value)}
              aria-label="Конец периода"
              className="h-9 rounded-lg border border-med-border bg-med-surface px-2 text-xs text-med-text-primary outline-none transition-colors focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
            />
          </label>
        </div>
      )}
    </div>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <section
      role="alert"
      className="flex flex-col items-center justify-center rounded-xl border border-med-error/30 bg-med-surface px-6 py-12 text-center shadow-med-card"
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-med-error/10 text-med-error">
        <AlertTriangle className="h-7 w-7" />
      </div>
      <h2 className="mt-4 text-xl font-semibold leading-7 text-med-text-primary">
        Не удалось загрузить список пробелов
      </h2>
      <p className="mt-1 max-w-[440px] text-sm leading-5 text-med-text-secondary">
        Проверьте соединение и попробуйте ещё раз. Данные не изменены.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg bg-med-primary px-4 text-sm font-semibold text-white transition-colors hover:bg-med-primary-hover"
      >
        <RefreshCw className="h-4 w-4" />
        Повторить
      </button>
    </section>
  );
}

function DeveloperLoading() {
  return (
    <section
      className="rounded-xl border border-med-border bg-med-surface p-6 shadow-med-card"
      aria-busy="true"
      aria-label="Загрузка технического списка"
    >
      <div className="h-6 w-56 animate-pulse rounded bg-med-bg" />
      <div className="mt-2 h-3 w-80 animate-pulse rounded bg-med-bg" />
      <div className="mt-5 space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="h-12 animate-pulse rounded-lg bg-med-bg" />
        ))}
      </div>
    </section>
  );
}

export function KnowledgeGapsPage() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const initialDebugState = params.get('state');
  const initialRole: AdminRole =
    params.get('role') === 'developer' ? 'developer' : 'kb_owner';
  const initialPeriod = parsePeriod(params.get('period'));
  const initialSort = parseSort(params.get('sort'));
  const initialStatuses = parseStatusFilter(params.get('status'));

  const [role, setRole] = useState<AdminRole>(initialRole);
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);
  const [period, setPeriod] = useState<GapPeriod>(initialPeriod);
  const [customFrom, setCustomFrom] = useState(() =>
    toDateInputValue(new Date(Date.now() - 7 * DAY_MS)),
  );
  const [customTo, setCustomTo] = useState(() => toDateInputValue(new Date()));
  const [filters, setFilters] = useState<GapFilters>(() => ({
    search: params.get('search') ?? '',
    statuses: initialStatuses,
    sources: [...DEFAULT_FILTERS.sources],
    reasons: [...DEFAULT_FILTERS.reasons],
  }));
  const [sort, setSort] = useState<GapSort>(initialSort);
  const [forceEmpty, setForceEmpty] = useState(initialDebugState === 'empty');
  const [pageState, setPageState] = useState<PageState>('loading');
  const [selectedGapId, setSelectedGapId] = useState<string | null>(() => {
    if (initialRole === 'developer' || params.get('panel') === 'closed') return null;
    return params.get('gap');
  });
  const [resolveTarget, setResolveTarget] = useState<KnowledgeGap | null>(null);
  const [dismissTarget, setDismissTarget] = useState<KnowledgeGap | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  const failNextLoadRef = useRef(initialDebugState === 'error');
  const debugLoadingRef = useRef(initialDebugState === 'loading');

  const loadGaps = useCallback(async () => {
    setPageState('loading');

    // Для дебага: ?state=error → сразу ошибка
    if (failNextLoadRef.current) {
      failNextLoadRef.current = false;
      setPageState('error');
      return;
    }
    // Для дебага: ?state=loading → долгая загрузка
    if (debugLoadingRef.current) {
      await new Promise((resolve) => window.setTimeout(resolve, 60_000));
    }

    try {
      const loaded = await fetchKnowledgeGaps();
      setGaps(loaded);
      setPageState('ready');
    } catch {
      setPageState('error');
    }
  }, []);

  useEffect(() => {
    void loadGaps();
  }, [loadGaps]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'Карта пробелов — MedTrust';
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const range = useMemo(
    () => getPeriodRange(period, customFrom, customTo),
    [period, customFrom, customTo],
  );

  const periodGaps = useMemo(
    () =>
      gaps.filter((gap) => {
        const createdAt = new Date(gap.createdAt).getTime();
        return createdAt >= range.start && createdAt <= range.end;
      }),
    [gaps, range],
  );

  const visibleGaps = useMemo(() => {
    const filtered = periodGaps.filter((gap) => {
      if (!filters.statuses.includes(gap.status)) return false;
      if (!filters.sources.includes(gap.source)) return false;
      if (!filters.reasons.includes(gap.reason)) return false;

      const search = filters.search.trim().toLowerCase().replace(/ё/g, 'е');
      if (!search) return true;

      return `${gap.rawQuestion} ${gap.resolvedQuery}`
        .toLowerCase()
        .replace(/ё/g, 'е')
        .includes(search);
    });

    const duration = (gap: KnowledgeGap) => {
      const end = gap.resolvedAt ? new Date(gap.resolvedAt).getTime() : Date.now();
      return end - new Date(gap.createdAt).getTime();
    };

    return [...filtered].sort((first, second) => {
      if (sort === 'newest') {
        return new Date(second.createdAt).getTime() - new Date(first.createdAt).getTime();
      }
      if (sort === 'oldest') {
        return new Date(first.createdAt).getTime() - new Date(second.createdAt).getTime();
      }
      return duration(second) - duration(first);
    });
  }, [filters, periodGaps, sort]);

  const metrics = useMemo(() => {
    const total = periodGaps.length;
    const open = periodGaps.filter((gap) => gap.status === 'open').length;
    const inReview = periodGaps.filter((gap) => gap.status === 'in_review').length;

    const resolvedInPeriod = gaps.filter(
      (gap) =>
        gap.status === 'resolved' &&
        gap.resolvedAt !== undefined &&
        new Date(gap.resolvedAt).getTime() >= range.start &&
        new Date(gap.resolvedAt).getTime() <= range.end,
    );

    const averageMs =
      resolvedInPeriod.length > 0
        ? resolvedInPeriod.reduce(
            (sum, gap) =>
              sum + (new Date(gap.resolvedAt as string).getTime() - new Date(gap.createdAt).getTime()),
            0,
          ) / resolvedInPeriod.length
        : null;

    return {
      total,
      open,
      inReview,
      resolved: resolvedInPeriod.length,
      averageLabel: averageMs === null ? '—' : formatDuration(averageMs),
    };
  }, [gaps, periodGaps, range]);

  const selectedGap = selectedGapId
    ? (gaps.find((gap) => gap.id === selectedGapId) ?? null)
    : null;

  const resetFilters = (resetPeriod = false) => {
    setFilters({
      search: '',
      statuses: [...DEFAULT_FILTERS.statuses],
      sources: [...DEFAULT_FILTERS.sources],
      reasons: [...DEFAULT_FILTERS.reasons],
    });
    setSort('newest');
    setForceEmpty(false);

    if (resetPeriod) {
      setPeriod('7d');
      setCustomFrom(toDateInputValue(new Date(Date.now() - 7 * DAY_MS)));
      setCustomTo(toDateInputValue(new Date()));
    }
  };

  const commitStatusChange = async (
    gap: KnowledgeGap,
    status: GapStatus,
    options?: StatusChangeOptions,
    onSuccess?: () => void,
  ) => {
    const run = async () => {
      const savedComment = await updateGapStatus(gap.id, status, {
        ...options,
        author: DEMO_ADMIN_USER.name,
      });

      const nowIso = new Date().toISOString();
      const isClosing = status === 'resolved' || status === 'dismissed';
      setGaps((current) =>
        current.map((item) => {
          if (item.id !== gap.id) return item;
          return {
            ...item,
            status,
            updatedAt: nowIso,
            ...(isClosing
              ? { resolvedAt: nowIso, resolvedBy: DEMO_ADMIN_USER.name }
              : {}),
            ...(savedComment ? { comments: [...item.comments, savedComment] } : {}),
          };
        }),
      );

      const messages: Record<GapStatus, string> = {
        open: 'Пробел снова открыт',
        in_review: 'Пробел переведён в работу',
        resolved: 'Пробел закрыт. Комментарий сохранён.',
        dismissed: 'Пробел отклонён. Запись осталась в истории.',
      };

      setToast({ id: Date.now(), type: 'success', message: messages[status] });
      onSuccess?.();
    };

    try {
      await run();
    } catch {
      const retry = () => {
        void commitStatusChange(gap, status, options, onSuccess).catch(() => undefined);
      };
      setToast({
        id: Date.now(),
        type: 'error',
        message: 'Не удалось сохранить изменения. Проверьте соединение.',
        actionLabel: 'Повторить',
        onAction: retry,
      });
      throw new Error('status-save-failed');
    }
  };

  const commitComment = async (gap: KnowledgeGap, comment: string) => {
    const run = async () => {
      const saved = await addGapComment(gap.id, comment, DEMO_ADMIN_USER.name);

      setGaps((current) =>
        current.map((item) =>
          item.id === gap.id
            ? { ...item, comments: [...item.comments, saved], updatedAt: saved.createdAt }
            : item,
        ),
      );
      setToast({ id: Date.now(), type: 'success', message: 'Комментарий сохранён' });
    };

    try {
      await run();
    } catch {
      const retry = () => {
        void commitComment(gap, comment).catch(() => undefined);
      };
      setToast({
        id: Date.now(),
        type: 'error',
        message: 'Не удалось сохранить комментарий. Проверьте соединение.',
        actionLabel: 'Повторить',
        onAction: retry,
      });
      throw new Error('comment-save-failed');
    }
  };

  const handleRequestStatus = (gap: KnowledgeGap, status: RequestedGapStatus) => {
    if (status === 'in_review') {
      void commitStatusChange(gap, 'in_review').catch(() => undefined);
      return;
    }
    if (status === 'resolved') {
      setDismissTarget(null);
      setResolveTarget(gap);
      return;
    }
    setResolveTarget(null);
    setDismissTarget(gap);
  };

  const handleResolveConfirm = async (note: string) => {
    if (!resolveTarget) return;
    await commitStatusChange(resolveTarget, 'resolved', { note }, () =>
      setResolveTarget(null),
    );
  };

  const handleDismissConfirm = async (reason: DismissReason, comment: string) => {
    if (!dismissTarget) return;

    const reasonLabel =
      DISMISS_REASON_OPTIONS.find((option) => option.value === reason)?.label ?? reason;
    const note = [reasonLabel, comment].filter(Boolean).join(' — ');

    await commitStatusChange(dismissTarget, 'dismissed', { note }, () =>
      setDismissTarget(null),
    );
  };

  const handleRoleChange = (nextRole: AdminRole) => {
    setRole(nextRole);
    setSelectedGapId(null);
    setResolveTarget(null);
    setDismissTarget(null);
    setToast(null);
  };

  const handleNavigate = (label: string) => {
    setToast({
      id: Date.now(),
      type: 'info',
      message: `Раздел «${label}» будет добавлен в следующей итерации.`,
    });
  };

  const handleLogout = () => {
    window.location.assign('/');
  };

  const copyToast = () => {
    setToast({ id: Date.now(), type: 'success', message: 'ID пробела скопирован' });
  };

  const periodLabelText = periodLabel(period);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-med-bg font-sans text-med-text-primary antialiased">
      <AdminHeader role={role} onRoleChange={handleRoleChange} onLogout={handleLogout} />

      <div className="flex min-h-0 flex-1">
        <AdminSidebar
          role={role}
          gapCount={gaps.filter((gap) => gap.status === 'open' || gap.status === 'in_review').length}
          onNavigate={handleNavigate}
          onLogout={handleLogout}
        />

        <main className="min-w-0 flex-1 overflow-y-auto bg-med-bg p-6">
          <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0">
                <nav
                  aria-label="Хлебные крошки"
                  className="flex flex-wrap items-center gap-1.5 text-sm text-med-text-secondary"
                >
                  <span>Админка</span>
                  <ChevronRight className="h-3.5 w-3.5 text-med-text-muted" />
                  <span>База знаний</span>
                  <ChevronRight className="h-3.5 w-3.5 text-med-text-muted" />
                  <span className="font-medium text-med-text-primary">Карта пробелов</span>
                </nav>

                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-semibold leading-8 tracking-tight text-med-text-primary">
                    Карта пробелов в базе знаний
                  </h1>
                  {role === 'developer' && (
                    <span className="rounded-full border border-med-border bg-med-primary-light/60 px-2.5 py-1 text-xs font-medium text-med-primary-hover">
                      Технический вид
                    </span>
                  )}
                </div>

                <p className="mt-1 max-w-[760px] text-sm leading-5 text-med-text-secondary">
                  {role === 'developer'
                    ? 'Обезличенный вид для разработчиков: query_id, тексты вопросов, причина недостаточности и статус. Персональные данные не отображаются.'
                    : 'Вопросы, на которые не нашлось достаточного ответа в корпоративной БЗ. Автоматические и подтверждённые пробелы.'}
                </p>
              </div>

              <PeriodSelector
                period={period}
                onPeriodChange={(next) => {
                  setPeriod(next);
                  setForceEmpty(false);
                }}
                customFrom={customFrom}
                customTo={customTo}
                onCustomFromChange={setCustomFrom}
                onCustomToChange={setCustomTo}
              />
            </div>

            {pageState === 'error' ? (
              <LoadError
                onRetry={() => {
                  void loadGaps();
                }}
              />
            ) : (
              <>
                {role === 'kb_owner' && (
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                    <MetricCard
                      label="Всего пробелов"
                      value={metrics.total}
                      hint={periodLabelText}
                      loading={pageState === 'loading'}
                    />
                    <MetricCard
                      label="Открыто"
                      value={metrics.open}
                      hint="ожидают решения"
                      loading={pageState === 'loading'}
                    />
                    <MetricCard
                      label="В работе"
                      value={metrics.inReview}
                      hint="на проверке"
                      loading={pageState === 'loading'}
                    />
                    <MetricCard
                      label="Закрыто"
                      value={metrics.resolved}
                      hint={periodLabelText}
                      loading={pageState === 'loading'}
                    />
                    <MetricCard
                      label="Среднее время закрытия"
                      value={metrics.averageLabel}
                      hint="от открытия до закрытия"
                      loading={pageState === 'loading'}
                    />
                  </div>
                )}

                {role === 'kb_owner' && (
                  <GapFilterBar
                    filters={filters}
                    onChange={(next) => {
                      setFilters((current) => ({ ...current, ...next }));
                      setForceEmpty(false);
                    }}
                    sort={sort}
                    onSortChange={setSort}
                    onReset={() => resetFilters(false)}
                  />
                )}

                {pageState === 'loading' ? (
                  role === 'developer' ? (
                    <DeveloperLoading />
                  ) : (
                    <GapTableSkeleton />
                  )
                ) : role === 'developer' ? (
                  <DeveloperGapsView gaps={periodGaps} periodLabel={periodLabelText} />
                ) : forceEmpty || visibleGaps.length === 0 ? (
                  <EmptyState onReset={() => resetFilters(true)} />
                ) : (
                  <GapTable
                    gaps={visibleGaps}
                    totalCount={periodGaps.length}
                    selectedId={selectedGapId}
                    onOpen={(gap) => setSelectedGapId(gap.id)}
                    onRequestStatus={handleRequestStatus}
                    onCopyId={copyToast}
                  />
                )}
              </>
            )}
          </div>
        </main>
      </div>

      {role === 'kb_owner' && selectedGap && (
        <GapDetailPanel
          gap={selectedGap}
          onClose={() => setSelectedGapId(null)}
          onRequestStatus={handleRequestStatus}
          onSaveComment={commitComment}
          onCopyId={copyToast}
          closeOnEscape={!resolveTarget && !dismissTarget}
        />
      )}

      {resolveTarget && (
        <ConfirmResolveModal
          gap={resolveTarget}
          onClose={() => setResolveTarget(null)}
          onConfirm={handleResolveConfirm}
        />
      )}

      {dismissTarget && (
        <DismissGapModal
          gap={dismissTarget}
          onClose={() => setDismissTarget(null)}
          onConfirm={handleDismissConfirm}
        />
      )}

      {toast && (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          actionLabel={toast.actionLabel}
          onAction={toast.onAction}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
