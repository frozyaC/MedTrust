import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  BookOpen,
  CheckCircle2,
  Globe,
  Info,
  MessageSquare,
  Play,
  X,
  XCircle,
} from 'lucide-react';
import { KnowledgeGap } from '../../types/knowledgeGaps';
import { shortId } from '../../lib/format';
import { lockBodyScroll } from '../../lib/scrollLock';
import { CopyButton } from './CopyButton';
import { SourceBadge, StatusBadge } from './GapBadges';
import { GapStatusTimeline } from './GapStatusTimeline';
import type { RequestedGapStatus } from './GapTable';

interface GapDetailPanelProps {
  gap: KnowledgeGap;
  onClose: () => void;
  onRequestStatus: (gap: KnowledgeGap, status: RequestedGapStatus) => void;
  onSaveComment: (gap: KnowledgeGap, comment: string) => Promise<void>;
  onCopyId: () => void;
  closeOnEscape?: boolean;
}

function PanelSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-med-text-muted">
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function IdRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[132px] shrink-0 text-xs font-medium text-med-text-muted">{label}</span>
      <span
        className="min-w-0 flex-1 truncate font-mono text-xs text-med-text-secondary"
        title={value}
      >
        {value || '—'}
      </span>
      {value && (
        <CopyButton
          value={value}
          className="inline-flex shrink-0 items-center rounded p-0.5 text-med-text-muted transition-colors hover:bg-med-bg hover:text-med-primary"
        />
      )}
    </div>
  );
}

export function GapDetailPanel({
  gap,
  onClose,
  onRequestStatus,
  onSaveComment,
  onCopyId,
  closeOnEscape = true,
}: GapDetailPanelProps) {
  const [comment, setComment] = useState(gap.ownerComment);
  const [savingComment, setSavingComment] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  useEffect(() => {
    setComment(gap.ownerComment);
    setCommentError(null);
  }, [gap.id, gap.ownerComment]);

  useEffect(() => lockBodyScroll(), []);

  useEffect(() => {
    if (!closeOnEscape) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closeOnEscape, onClose]);

  const isClosed = gap.status === 'resolved' || gap.status === 'dismissed';
  const commentDirty = comment !== gap.ownerComment;

  const handleSaveComment = async () => {
    if (!commentDirty || savingComment) return;

    setSavingComment(true);
    setCommentError(null);
    try {
      await onSaveComment(gap, comment);
    } catch {
      setCommentError('Не удалось сохранить комментарий. Попробуйте ещё раз.');
    } finally {
      setSavingComment(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 animate-fade-in bg-med-text-primary/25 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="gap-detail-title"
        className="absolute inset-y-3 right-3 flex w-[480px] max-w-[calc(100vw-24px)] animate-panel-in flex-col overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-med-border px-6 py-4">
          <div className="min-w-0">
            <h2
              id="gap-detail-title"
              className="text-xl font-semibold leading-7 tracking-tight text-med-text-primary"
            >
              Пробел в БЗ
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <SourceBadge source={gap.source} />
              <StatusBadge status={gap.status} />
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-text-primary"
            aria-label="Закрыть карточку пробела"
            title="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
          {gap.source === 'automatic' && (
            <div className="flex gap-2 rounded-lg border border-med-border bg-med-primary-light/50 px-3 py-2.5 text-xs leading-5 text-med-text-secondary">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-med-primary" />
              <span>
                Пробел зафиксирован автоматически. Подтверждение регистратора не требуется.
              </span>
            </div>
          )}

          <PanelSection title="Вопрос">
            <div className="rounded-lg border border-med-border bg-med-bg/40 p-3">
              <p className="text-base leading-6 text-med-text-primary">{gap.rawQuestion}</p>

              <div className="mt-3 border-t border-med-border/70 pt-2.5">
                <div className="text-xs uppercase tracking-wide text-med-text-muted">
                  Нормализованный запрос
                </div>
                <p className="mt-1 text-sm leading-5 text-med-text-secondary">
                  {gap.resolvedQuery || '—'}
                </p>
              </div>
            </div>

            <div className="flex gap-2 text-sm leading-5 text-med-text-secondary">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-med-primary" />
              <span>{gap.answerabilityReason}</span>
            </div>

            {typeof gap.confidence === 'number' && (
              <div className="text-xs leading-4 text-med-text-muted">
                Уверенность нормализации: {Math.round(gap.confidence * 100)}%
              </div>
            )}
          </PanelSection>

          <PanelSection title="Связи">
            <div className="space-y-1.5 rounded-lg border border-med-border bg-med-surface p-2.5">
              <IdRow label="query_id" value={gap.queryId} />
              <IdRow label="conversation_id" value={gap.conversationId} />
              <IdRow label="source_message_id" value={gap.sourceMessageId} />
            </div>
          </PanelSection>

          <PanelSection title="Источники">
            {gap.sourceIds.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {gap.sourceIds.map((source) => (
                  <span
                    key={source.id}
                    title={source.id}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-med-border bg-med-bg/70 px-2.5 py-1 text-xs text-med-text-secondary"
                  >
                    <BookOpen className="h-3.5 w-3.5 shrink-0 text-med-primary" />
                    <span className="truncate">{source.title}</span>
                  </span>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-med-border bg-med-bg/40 px-3 py-3 text-sm text-med-text-secondary">
                Релевантные источники не найдены
              </div>
            )}

            {gap.webSearchUsed && (
              <div className="flex gap-2 rounded-lg border border-med-warning/40 bg-med-warning/10 px-3 py-2.5 text-xs leading-5 text-med-text-primary">
                <Globe className="mt-0.5 h-4 w-4 shrink-0 text-med-warning" />
                <span>Ответ сформирован с Web Search, требует проверки</span>
              </div>
            )}
          </PanelSection>

          {gap.source === 'user_feedback' && (
            <PanelSection title="Обратная связь">
              {gap.feedback ? (
                <div className="space-y-2 rounded-lg border border-med-border bg-med-bg/40 p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-med-text-muted">feedback_id</span>
                    <span
                      className="min-w-0 flex-1 truncate font-mono text-xs text-med-text-secondary"
                      title={gap.feedback.id}
                    >
                      {gap.feedback.id}
                    </span>
                    <CopyButton
                      value={gap.feedback.id}
                      className="inline-flex shrink-0 items-center rounded p-0.5 text-med-text-muted transition-colors hover:bg-med-surface hover:text-med-primary"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-med-text-muted">Оценка</span>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${
                        gap.feedback.rating === 'negative'
                          ? 'border-med-error/30 bg-med-error/10 text-med-text-primary'
                          : 'border-med-success/30 bg-med-success/10 text-med-text-primary'
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          gap.feedback.rating === 'negative' ? 'bg-med-error' : 'bg-med-success'
                        }`}
                      />
                      {gap.feedback.rating === 'negative' ? 'Негативная' : 'Положительная'}
                    </span>
                  </div>

                  {gap.feedback.comment && (
                    <blockquote className="border-l-2 border-med-border pl-2.5 text-sm leading-5 text-med-text-secondary">
                      «{gap.feedback.comment}»
                    </blockquote>
                  )}
                </div>
              ) : (
                <p className="text-sm text-med-text-secondary">Данные обратной связи не приложены.</p>
              )}
            </PanelSection>
          )}

          <PanelSection
            title="Комментарий владельца БЗ"
            action={
              <span className="text-xs text-med-text-muted">
                {commentDirty ? 'Не сохранён' : 'Сохранён'}
              </span>
            }
          >
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              maxLength={1000}
              rows={3}
              placeholder="Например: подготовить статью о возврате предоплаты"
              className="w-full resize-y rounded-lg border border-med-border bg-med-surface p-3 text-sm leading-5 text-med-text-primary outline-none transition-colors placeholder:text-med-text-muted focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
            />

            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-med-text-muted">{comment.length}/1000</span>
              <button
                type="button"
                onClick={() => void handleSaveComment()}
                disabled={!commentDirty || savingComment}
                className="inline-flex items-center gap-1.5 rounded-lg border border-med-border-strong bg-med-surface px-3 py-1.5 text-xs font-semibold text-med-primary transition-colors hover:bg-med-primary-light/40 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                {savingComment ? 'Сохраняем…' : 'Сохранить комментарий'}
              </button>
            </div>

            {commentError && <p className="text-xs text-med-error">{commentError}</p>}
          </PanelSection>

          <PanelSection title="История">
            <GapStatusTimeline gap={gap} />
          </PanelSection>
        </div>

        <footer className="border-t border-med-border bg-med-surface px-6 py-3">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => onRequestStatus(gap, 'in_review')}
              disabled={gap.status !== 'open'}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-med-border-strong bg-med-surface px-3 text-sm font-semibold text-med-primary transition-colors hover:bg-med-primary-light/40 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              Взять в работу
            </button>

            <button
              type="button"
              onClick={() => onRequestStatus(gap, 'resolved')}
              disabled={isClosed}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-med-primary px-3 text-sm font-semibold text-white transition-colors hover:bg-med-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              Закрыть пробел
            </button>

            <button
              type="button"
              onClick={() => onRequestStatus(gap, 'dismissed')}
              disabled={isClosed}
              className="col-span-2 inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-med-error/30 bg-med-surface px-3 text-sm font-semibold text-med-error transition-colors hover:bg-med-error/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              Отклонить
            </button>
          </div>

          <div className="mt-3 flex items-center justify-between gap-2">
            <CopyButton
              value={gap.id}
              label="Скопировать ID"
              onCopied={onCopyId}
              className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-medium text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-primary"
            />
            <span className="truncate font-mono text-xs text-med-text-muted">
              {shortId(gap.id)}
            </span>
          </div>
        </footer>
      </aside>
    </div>
  );
}
