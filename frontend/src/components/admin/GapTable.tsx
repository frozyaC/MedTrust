import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  CheckCircle2,
  ExternalLink,
  Eye,
  MoreHorizontal,
  Play,
  XCircle,
} from 'lucide-react';
import { KnowledgeGap } from '../../types/knowledgeGaps';
import { formatDateTime, formatDayLabel, formatTime, shortId } from '../../lib/format';
import { CopyButton } from './CopyButton';
import { ReasonBadge, SourceBadge, StatusBadge } from './GapBadges';

export type RequestedGapStatus = 'in_review' | 'resolved' | 'dismissed';

interface GapTableProps {
  gaps: KnowledgeGap[];
  totalCount: number;
  selectedId: string | null;
  onOpen: (gap: KnowledgeGap) => void;
  onRequestStatus: (gap: KnowledgeGap, status: RequestedGapStatus) => void;
  onCopyId?: () => void;
}

interface RowStatusMenuProps {
  gap: KnowledgeGap;
  onOpen: (gap: KnowledgeGap) => void;
  onRequestStatus: (gap: KnowledgeGap, status: RequestedGapStatus) => void;
}

const MENU_WIDTH = 208;
const MENU_HEIGHT = 196;

function RowStatusMenu({ gap, onOpen, onRequestStatus }: RowStatusMenuProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const updatePosition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;

      let top = rect.bottom + 6;
      if (top + MENU_HEIGHT > window.innerHeight - 8) {
        top = Math.max(8, rect.top - MENU_HEIGHT - 6);
      }
      const left = Math.min(
        window.innerWidth - MENU_WIDTH - 8,
        Math.max(8, rect.right - MENU_WIDTH),
      );

      setCoords({ top, left });
    };

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    updatePosition();
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  const close = () => setOpen(false);
  const isClosed = gap.status === 'resolved' || gap.status === 'dismissed';

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-primary"
        title="Быстрые действия"
        aria-label="Быстрые действия"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{ position: 'fixed', top: coords.top, left: coords.left, width: MENU_WIDTH }}
            className="z-[65] animate-fade-in rounded-xl border border-med-border bg-med-surface p-1.5 shadow-med-panel"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                onOpen(gap);
                close();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-med-text-primary transition-colors hover:bg-med-bg"
            >
              <Eye className="h-4 w-4 text-med-text-secondary" />
              Открыть карточку
            </button>

            <div className="my-1 border-t border-med-border/70" />

            <button
              type="button"
              role="menuitem"
              disabled={gap.status !== 'open'}
              onClick={() => {
                onRequestStatus(gap, 'in_review');
                close();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-med-text-primary transition-colors hover:bg-med-bg disabled:cursor-not-allowed disabled:text-med-text-muted disabled:hover:bg-transparent"
            >
              <Play className="h-4 w-4" />
              Взять в работу
            </button>

            <button
              type="button"
              role="menuitem"
              disabled={isClosed}
              onClick={() => {
                onRequestStatus(gap, 'resolved');
                close();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-med-text-primary transition-colors hover:bg-med-bg disabled:cursor-not-allowed disabled:text-med-text-muted disabled:hover:bg-transparent"
            >
              <CheckCircle2 className="h-4 w-4" />
              Закрыть пробел
            </button>

            <button
              type="button"
              role="menuitem"
              disabled={isClosed}
              onClick={() => {
                onRequestStatus(gap, 'dismissed');
                close();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-med-error transition-colors hover:bg-med-error/10 disabled:cursor-not-allowed disabled:text-med-text-muted disabled:hover:bg-transparent"
            >
              <XCircle className="h-4 w-4" />
              Отклонить
            </button>
          </div>,
          document.body,
        )}
    </>
  );
}

function GapRow({
  gap,
  index,
  selected,
  onOpen,
  onRequestStatus,
  onCopyId,
}: {
  gap: KnowledgeGap;
  index: number;
  selected: boolean;
  onOpen: (gap: KnowledgeGap) => void;
  onRequestStatus: (gap: KnowledgeGap, status: RequestedGapStatus) => void;
  onCopyId?: () => void;
}) {
  return (
    <tr
      tabIndex={0}
      aria-label={`Открыть пробел ${shortId(gap.id)}`}
      onClick={() => onOpen(gap)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen(gap);
        }
      }}
      className={`group cursor-pointer border-t border-med-border/70 outline-none transition-colors hover:bg-med-primary/5 focus-visible:bg-med-primary-light/30 ${
        selected
          ? 'bg-med-primary-light/40'
          : index % 2 === 1
            ? 'bg-med-bg/30'
            : 'bg-med-surface'
      }`}
    >
      <td className="px-2.5 py-3 align-middle">
        <div className="flex items-center gap-0.5">
          <span
            className="truncate font-mono text-xs text-med-text-secondary"
            title={gap.id}
          >
            {shortId(gap.id)}
          </span>
          <CopyButton
            value={gap.id}
            onCopied={onCopyId}
            className="inline-flex shrink-0 items-center rounded p-0.5 text-med-text-muted opacity-60 transition-all hover:bg-med-bg hover:text-med-primary group-hover:opacity-100"
          />
        </div>
      </td>

      <td className="px-2.5 py-3 align-middle">
        <div className="flex items-start gap-1.5">
          <span
            className="line-clamp-2 min-w-0 text-sm leading-5 text-med-text-primary"
            title={gap.rawQuestion}
          >
            {gap.rawQuestion}
          </span>
          {gap.webSearchUsed && (
            <span
              className="mt-0.5 inline-flex shrink-0 items-center justify-center rounded-full bg-med-warning/10 p-0.5 text-med-warning"
              title="Ответ сформирован с Web Search, требует проверки"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">Использован Web Search</span>
            </span>
          )}
        </div>
      </td>

      <td className="px-2.5 py-3 align-middle">
        <span
          className="line-clamp-2 text-sm leading-5 text-med-text-secondary"
          title={gap.resolvedQuery}
        >
          {gap.resolvedQuery || '—'}
        </span>
      </td>

      <td className="px-2.5 py-3 align-middle">
        <SourceBadge source={gap.source} />
      </td>

      <td className="px-2.5 py-3 align-middle">
        <ReasonBadge reason={gap.reason} />
      </td>

      <td className="px-2.5 py-3 align-middle">
        <StatusBadge status={gap.status} />
      </td>

      <td className="px-2.5 py-3 align-middle" title={formatDateTime(gap.createdAt)}>
        <div className="whitespace-nowrap text-xs text-med-text-secondary">
          {formatDayLabel(gap.createdAt)}
        </div>
        <div className="whitespace-nowrap text-xs text-med-text-muted">
          {formatTime(gap.createdAt)}
        </div>
      </td>

      <td className="px-2.5 py-3 align-middle" title={formatDateTime(gap.updatedAt)}>
        <div className="whitespace-nowrap text-xs text-med-text-secondary">
          {formatDayLabel(gap.updatedAt)}
        </div>
        <div className="whitespace-nowrap text-xs text-med-text-muted">
          {formatTime(gap.updatedAt)}
        </div>
      </td>

      <td className="px-2 py-3 align-middle" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-end gap-1">
          <button
            type="button"
            onClick={() => onOpen(gap)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-primary"
            title="Открыть карточку"
            aria-label="Открыть карточку"
          >
            <Eye className="h-4 w-4" />
          </button>
          <RowStatusMenu gap={gap} onOpen={onOpen} onRequestStatus={onRequestStatus} />
        </div>
      </td>
    </tr>
  );
}

export function GapTable({
  gaps,
  totalCount,
  selectedId,
  onOpen,
  onRequestStatus,
  onCopyId,
}: GapTableProps) {
  return (
    <section className="overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-med-border px-4 py-3">
        <div>
          <h2 className="text-xl font-semibold leading-7 text-med-text-primary">Пробелы</h2>
          <p className="text-xs leading-4 text-med-text-muted">
            Показано {gaps.length} из {totalCount} за период
          </p>
        </div>
        <p className="text-xs leading-4 text-med-text-muted">
          Клик по строке открывает карточку
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1062px] table-fixed border-collapse text-left">
          <colgroup>
            <col className="w-[96px]" />
            <col className="w-[176px]" />
            <col className="w-[150px]" />
            <col className="w-[138px]" />
            <col className="w-[170px]" />
            <col className="w-[98px]" />
            <col className="w-[82px]" />
            <col className="w-[82px]" />
            <col className="w-[70px]" />
          </colgroup>
          <thead className="bg-med-bg/50">
            <tr>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                ID
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Исходный вопрос
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Нормализованный запрос
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Источник
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Причина
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Статус
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Создан
              </th>
              <th className="px-2.5 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Обновлён
              </th>
              <th className="px-2 py-2.5">
                <span className="sr-only">Действия</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {gaps.map((gap, index) => (
              <GapRow
                key={gap.id}
                gap={gap}
                index={index}
                selected={selectedId === gap.id}
                onOpen={onOpen}
                onRequestStatus={onRequestStatus}
                onCopyId={onCopyId}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function GapTableSkeleton() {
  return (
    <section
      className="overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-card"
      aria-busy="true"
      aria-label="Загрузка списка пробелов"
    >
      <div className="flex items-center justify-between border-b border-med-border px-4 py-3">
        <div className="space-y-2">
          <div className="h-5 w-28 animate-pulse rounded bg-med-bg" />
          <div className="h-3 w-44 animate-pulse rounded bg-med-bg" />
        </div>
        <div className="h-3 w-48 animate-pulse rounded bg-med-bg" />
      </div>

      <div className="overflow-hidden">
        <div className="min-w-[1080px]">
          <div className="grid grid-cols-[96px_176px_150px_138px_170px_98px_82px_82px_70px] gap-2 border-b border-med-border bg-med-bg/40 px-3 py-3">
            {Array.from({ length: 9 }).map((_, index) => (
              <div key={index} className="h-3 animate-pulse rounded bg-med-border/60" />
            ))}
          </div>

          {Array.from({ length: 6 }).map((_, row) => (
            <div
              key={row}
              className="grid grid-cols-[96px_176px_150px_138px_170px_98px_82px_82px_70px] items-center gap-2 border-t border-med-border/60 px-3 py-4"
            >
              <div className="h-3 w-14 animate-pulse rounded bg-med-bg" />
              <div className="space-y-1.5">
                <div className="h-3 w-full animate-pulse rounded bg-med-bg" />
                <div className="h-3 w-3/4 animate-pulse rounded bg-med-bg" />
              </div>
              <div className="space-y-1.5">
                <div className="h-3 w-full animate-pulse rounded bg-med-bg" />
                <div className="h-3 w-2/3 animate-pulse rounded bg-med-bg" />
              </div>
              <div className="h-6 w-20 animate-pulse rounded-full bg-med-bg" />
              <div className="h-6 w-28 animate-pulse rounded-full bg-med-bg" />
              <div className="h-6 w-16 animate-pulse rounded-full bg-med-bg" />
              <div className="space-y-1.5">
                <div className="h-3 w-16 animate-pulse rounded bg-med-bg" />
                <div className="h-3 w-10 animate-pulse rounded bg-med-bg" />
              </div>
              <div className="space-y-1.5">
                <div className="h-3 w-16 animate-pulse rounded bg-med-bg" />
                <div className="h-3 w-10 animate-pulse rounded bg-med-bg" />
              </div>
              <div className="h-7 w-14 animate-pulse rounded bg-med-bg" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
