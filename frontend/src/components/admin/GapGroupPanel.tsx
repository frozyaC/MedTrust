import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, RefreshCw, X } from 'lucide-react';
import {
  confirmGapGroup, detachGapGroupMember, fetchGapGroup, GapApiError, gapGroupErrorMessage, resolveGapGroup,
} from '../../api/knowledgeGaps';
import type { GapGroupResolveRequest, KnowledgeGapGroup } from '../../types/knowledgeGaps';
import { formatDateTime } from '../../lib/format';
import { lockBodyScroll } from '../../lib/scrollLock';
import { StatusBadge } from './GapBadges';

export const GROUP_STATUS_LABELS = {
  candidate: 'Ожидает подтверждения', open: 'Открыта', in_review: 'В работе',
  resolved: 'Закрыта', dismissed: 'Отклонена',
};

const buttonClass = 'rounded-lg border border-med-border px-3 py-2 text-sm hover:bg-med-bg disabled:cursor-not-allowed disabled:opacity-50';
const inputClass = 'w-full rounded-lg border border-med-border bg-med-surface p-3 text-sm outline-none focus:border-med-primary';

interface Props {
  groupId: number;
  author: string;
  onClose: () => void;
  onOpenGap: (gapId: number) => void;
  onChanged: () => Promise<void>;
}

export function GapGroupPanel({ groupId, author, onClose, onOpenGap, onChanged }: Props) {
  const [group, setGroup] = useState<KnowledgeGapGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number[]>([]);
  const [note, setNote] = useState('');
  const [detachId, setDetachId] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement>(null);
  const pendingResolve = useRef<{ signature: string; request: GapGroupResolveRequest } | null>(null);

  const load = useCallback(async () => {
    const loaded = await fetchGapGroup(groupId);
    setGroup(loaded);
    setStale(false);
    setSelected(loaded.members.filter((m) => !m.removedAt && ['open', 'in_review'].includes(m.status)).map((m) => m.gapId));
  }, [groupId]);

  useEffect(() => {
    void load().catch((err) => setError(gapGroupErrorMessage(err))).finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const release = lockBodyScroll();
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => { release(); previous?.focus(); };
  }, []);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busyRef.current) onClose();
      if (event.key !== 'Tab') return;
      const focusable = panelRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [tabindex="0"]');
      if (!focusable?.length) { event.preventDefault(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panelRef.current)) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const retryLoad = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try { await Promise.all([load(), onChanged()]); } catch (err) { setError(gapGroupErrorMessage(err)); }
    finally { busyRef.current = false; setBusy(false); }
  };

  const mutate = async (action: () => Promise<unknown>, message: string) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setStale(true);
      pendingResolve.current = null;
      setNote('');
      setDetachId(null);
      setReason('');
      setSuccess(message);
      const refreshed = await Promise.allSettled([load(), onChanged()]);
      if (refreshed.some((result) => result.status === 'rejected')) {
        setError('Изменения сохранены, но не все данные удалось обновить. Нажмите «Обновить данные».');
      }
    } catch (err) {
      setError(gapGroupErrorMessage(err));
      if (err instanceof GapApiError && err.status === 409) setStale(true);
    } finally { busyRef.current = false; setBusy(false); }
  };

  const closeSelected = () => {
    const body = { member_ids: [...selected].sort((a, b) => a - b), note: note.trim(), author };
    const signature = JSON.stringify(body);
    if (pendingResolve.current?.signature !== signature) {
      // getRandomValues also works when the app is served over HTTP on a LAN.
      const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('');
      pendingResolve.current = { signature, request: { ...body, idempotency_key: key } };
    }
    const request = pendingResolve.current.request;
    void mutate(() => resolveGapGroup(groupId, request), 'Выбранные пробелы закрыты.');
  };

  const active = group?.members.filter((m) => !m.removedAt) ?? [];
  const removed = group?.members.filter((m) => m.removedAt) ?? [];
  const selectable = active.filter((m) => ['open', 'in_review'].includes(m.status));
  const candidate = group?.status === 'candidate';
  const canResolve = Boolean(group?.confirmedAt && ['open', 'in_review'].includes(group.status));

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-med-text-primary/25 backdrop-blur-[1px]" aria-hidden="true" onClick={() => { if (!busyRef.current) onClose(); }} />
      <aside ref={panelRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="gap-group-title"
        className="absolute inset-y-3 right-3 flex w-[560px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-panel outline-none">
        <header className="flex items-start justify-between gap-3 border-b border-med-border p-5">
          <div><h2 id="gap-group-title" className="text-xl font-semibold">Группа пробелов</h2>
            {group && <p className="mt-1 text-sm text-med-text-secondary">{GROUP_STATUS_LABELS[group.status]}</p>}</div>
          <button type="button" className={buttonClass} disabled={busy} aria-label="Закрыть группу" onClick={onClose}><X className="h-4 w-4" /></button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5" aria-busy={loading || busy}>
          {loading && <p role="status">Загрузка группы…</p>}
          {success && <p role="status" className="rounded-lg bg-med-success/10 p-3 text-sm">{success}</p>}
          {error && <div role="alert" className="space-y-2 rounded-lg border border-med-error/30 p-3 text-sm">
            <p>{error}</p><button className={buttonClass} disabled={busy} onClick={() => void retryLoad()}>Обновить данные</button>
          </div>}
          {group && <>
            <h3 className="text-lg font-medium">{group.title}</h3>
            <p className="text-xs text-med-text-muted">Активных участников: {group.activeMemberCount} · Обновлена {formatDateTime(group.updatedAt)}</p>
            {group.confirmedAt && <p className="text-xs text-med-text-secondary">Подтвердил: {group.confirmedBy || '—'} · {formatDateTime(group.confirmedAt)}</p>}
            {candidate && <p className="rounded-lg bg-med-primary-light/50 p-3 text-sm">Выберите минимум два пробела с одной проблемой. Невыбранные участники будут исключены из предложения.</p>}
            {!candidate && !group.confirmedAt && group.status !== 'dismissed' && <p className="text-sm text-med-text-secondary">Подтверждение группы не зафиксировано. Совместное закрытие недоступно.</p>}
            <fieldset disabled={busy || stale} className="space-y-3">
              <legend className="mb-2 text-sm font-semibold">Участники</legend>
              {(candidate || canResolve) && <button type="button" className={buttonClass} onClick={() => setSelected(selected.length === selectable.length ? [] : selectable.map((m) => m.gapId))}>
                {selected.length === selectable.length ? 'Снять выбор' : 'Выбрать все незакрытые'}
              </button>}
              {active.map((member) => <div key={member.gapId} className="space-y-2 rounded-lg border border-med-border p-3">
                <div className="flex items-start gap-2">
                  {(candidate || canResolve) && <input type="checkbox" className="mt-1" aria-label={`Выбрать пробел ${member.gapId}`}
                    disabled={!['open', 'in_review'].includes(member.status)} checked={selected.includes(member.gapId)}
                    onChange={(event) => setSelected((ids) => event.target.checked ? [...ids, member.gapId] : ids.filter((id) => id !== member.gapId))} />}
                  <button type="button" className="text-left text-sm font-medium text-med-primary hover:underline" onClick={() => onOpenGap(member.gapId)}>{member.question}</button>
                </div>
                <StatusBadge status={member.status} />
                <p className="text-xs text-med-text-secondary">Обращений: {member.occurrenceCount} · Сходство: {member.similarity.toFixed(2)}</p>
                {(candidate || canResolve) && <button type="button" className="text-xs text-med-error hover:underline" onClick={() => { setDetachId(member.gapId); setReason(''); }}>Исключить из группы</button>}
                {detachId === member.gapId && <div className="space-y-2">
                  <label className="block text-sm">Причина исключения
                    <textarea className={inputClass} value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} />
                  </label>
                  <div className="flex gap-2">
                    <button type="button" className={buttonClass} disabled={!reason.trim()} onClick={() => void mutate(
                      () => detachGapGroupMember(groupId, member.gapId, { reason: reason.trim(), author }), 'Участник исключён из группы.',
                    )}>Исключить участника</button>
                    <button type="button" className={buttonClass} onClick={() => setDetachId(null)}>Отмена</button>
                  </div>
                </div>}
              </div>)}
              {candidate && <button type="button" className={`${buttonClass} bg-med-primary text-white`} disabled={selected.length < 2} onClick={() => void mutate(
                () => confirmGapGroup(groupId, { member_ids: selected, author }), 'Состав группы подтверждён.',
              )}>Подтвердить группу ({selected.length})</button>}
              {canResolve && <div className="space-y-2 border-t border-med-border pt-3">
                <label className="block text-sm">Что было сделано
                  <textarea className={inputClass} value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} placeholder="Например: добавлены правила подготовки к биохимии" />
                </label>
                <p className="text-xs text-med-text-secondary">Комментарий обязателен. Будут закрыты только выбранные пробелы.</p>
                <button type="button" className={`${buttonClass} bg-med-primary text-white`} disabled={!selected.length || !note.trim()} onClick={closeSelected}>Закрыть выбранные ({selected.length})</button>
              </div>}
            </fieldset>
            {removed.length > 0 && <details className="rounded-lg border border-med-border p-3">
              <summary className="cursor-pointer text-sm font-medium">История исключений ({removed.length})</summary>
              {removed.map((member) => <div key={member.gapId} className="mt-3 space-y-1 border-t border-med-border pt-2 text-sm">
                <p>{member.question}</p><p className="text-xs text-med-text-secondary">{member.removalReason === 'not_selected_on_confirmation' ? 'Не выбран при подтверждении' : member.removalReason}</p>
                <p className="text-xs text-med-text-muted">{member.removedBy || '—'} · {formatDateTime(member.removedAt!)}</p>
              </div>)}
            </details>}
          </>}
        </div>
        <footer className="flex items-center gap-2 border-t border-med-border p-4 text-sm">
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-label="Сохранение" />}
          <button type="button" className={`${buttonClass} inline-flex items-center gap-2`} disabled={busy || loading} onClick={() => void retryLoad()}><RefreshCw className="h-4 w-4" />Обновить данные</button>
        </footer>
      </aside>
    </div>
  );
}
