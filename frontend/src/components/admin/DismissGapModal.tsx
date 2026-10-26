import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, Loader2, X, XCircle } from 'lucide-react';
import { DismissReason, KnowledgeGap } from '../../types/knowledgeGaps';
import { DISMISS_REASON_OPTIONS } from '../../data/knowledgeGaps';
import { lockBodyScroll } from '../../lib/scrollLock';

interface DismissGapModalProps {
  gap: KnowledgeGap;
  onClose: () => void;
  onConfirm: (reason: DismissReason, comment: string) => Promise<void>;
}

export function DismissGapModal({ gap, onClose, onConfirm }: DismissGapModalProps) {
  const [reason, setReason] = useState<DismissReason | null>(null);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const firstOptionRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstOptionRef.current?.focus();
    return lockBodyScroll();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, saving]);

  const handleSubmit = async () => {
    if (!reason) {
      setError('Выберите причину отклонения.');
      firstOptionRef.current?.focus();
      return;
    }
    if (saving) return;

    setSaving(true);
    setError(null);
    try {
      await onConfirm(reason, comment.trim());
      onClose();
    } catch {
      setError('Не удалось сохранить изменения. Попробуйте ещё раз.');
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 animate-fade-in bg-med-text-primary/40 backdrop-blur-[2px]"
        onClick={() => {
          if (!saving) onClose();
        }}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dismiss-gap-title"
        className="relative w-full max-w-[520px] animate-slide-up rounded-xl border border-med-border bg-med-surface p-6 shadow-med-panel"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-med-error/10 text-med-error">
              <XCircle className="h-5 w-5" />
            </div>
            <div>
              <h2
                id="dismiss-gap-title"
                className="text-xl font-semibold leading-7 text-med-text-primary"
              >
                Отклонить пробел?
              </h2>
              <p className="mt-0.5 text-sm leading-5 text-med-text-secondary">
                Запись останется в истории, но не будет считаться пробелом.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Закрыть окно"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 rounded-lg border border-med-border bg-med-bg/40 px-3 py-2.5">
          <div className="text-xs uppercase tracking-wide text-med-text-muted">
            Исходный вопрос
          </div>
          <p className="mt-0.5 text-sm leading-5 text-med-text-primary">{gap.rawQuestion}</p>
        </div>

        <fieldset className="mt-4">
          <legend className="text-xs font-semibold text-med-text-primary">
            Причина отклонения <span className="text-med-error">*</span>
          </legend>

          <div className="mt-2 space-y-2">
            {DISMISS_REASON_OPTIONS.map((option, index) => {
              const checked = reason === option.value;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                    checked
                      ? 'border-med-primary bg-med-primary-light/40'
                      : 'border-med-border bg-med-surface hover:bg-med-bg'
                  }`}
                >
                  <input
                    ref={index === 0 ? firstOptionRef : undefined}
                    type="radio"
                    name="dismiss-reason"
                    value={option.value}
                    checked={checked}
                    onChange={() => {
                      setReason(option.value);
                      if (error) setError(null);
                    }}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-med-primary"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-med-text-primary">
                      {option.label}
                    </span>
                    <span className="block text-xs leading-4 text-med-text-secondary">
                      {option.description}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="mt-4 space-y-1.5">
          <label
            htmlFor="dismiss-gap-comment"
            className="block text-xs font-semibold text-med-text-primary"
          >
            Комментарий <span className="font-normal text-med-text-muted">(необязательно)</span>
          </label>
          <textarea
            id="dismiss-gap-comment"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="Коротко поясните решение"
            className="w-full resize-y rounded-lg border border-med-border bg-med-surface p-3 text-sm leading-5 text-med-text-primary outline-none transition-colors placeholder:text-med-text-muted focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
          />
        </div>

        {error && <p className="mt-3 text-xs text-med-error">{error}</p>}

        <div className="mt-4 flex gap-2 rounded-lg border border-med-warning/40 bg-med-warning/10 px-3 py-2.5 text-xs leading-5 text-med-text-primary">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-med-warning" />
          <span>Исходный вопрос и диагностические данные сохранятся в истории</span>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-med-border bg-med-surface px-4 text-sm font-semibold text-med-text-secondary transition-colors hover:border-med-border-strong hover:bg-med-bg disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={saving}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-med-error px-4 text-sm font-semibold text-white transition-colors hover:bg-med-error/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            {saving ? 'Сохраняем…' : 'Отклонить'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
