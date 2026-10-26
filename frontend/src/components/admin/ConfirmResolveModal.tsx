import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, CheckCircle2, Loader2, X } from 'lucide-react';
import { KnowledgeGap } from '../../types/knowledgeGaps';
import { lockBodyScroll } from '../../lib/scrollLock';

interface ConfirmResolveModalProps {
  gap: KnowledgeGap;
  onClose: () => void;
  onConfirm: (note: string) => Promise<void>;
}

export function ConfirmResolveModal({ gap, onClose, onConfirm }: ConfirmResolveModalProps) {
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
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
    if (!note.trim()) {
      setError('Опишите, что было сделано.');
      textareaRef.current?.focus();
      return;
    }
    if (saving) return;

    setSaving(true);
    setError(null);
    try {
      await onConfirm(note.trim());
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
        aria-labelledby="resolve-gap-title"
        className="relative w-full max-w-[520px] animate-slide-up rounded-xl border border-med-border bg-med-surface p-6 shadow-med-panel"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-med-success/10 text-med-success">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <h2
                id="resolve-gap-title"
                className="text-xl font-semibold leading-7 text-med-text-primary"
              >
                Закрыть пробел?
              </h2>
              <p className="mt-0.5 text-sm leading-5 text-med-text-secondary">
                Пробел будет переведён в статус «Закрыт».
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

        <div className="mt-4 space-y-1.5">
          <label
            htmlFor="resolve-gap-note"
            className="block text-xs font-semibold text-med-text-primary"
          >
            Что было сделано <span className="text-med-error">*</span>
          </label>
          <textarea
            id="resolve-gap-note"
            ref={textareaRef}
            value={note}
            onChange={(event) => {
              setNote(event.target.value);
              if (error) setError(null);
            }}
            rows={4}
            maxLength={1000}
            required
            aria-required="true"
            placeholder="Например: добавили статью о возврате предоплаты и обновили памятку"
            className="w-full resize-y rounded-lg border border-med-border bg-med-surface p-3 text-sm leading-5 text-med-text-primary outline-none transition-colors placeholder:text-med-text-muted focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
          />
          <div className="flex items-center justify-between gap-3">
            {error ? (
              <p className="text-xs text-med-error">{error}</p>
            ) : (
              <span className="text-xs text-med-text-muted">
                Комментарий сохранится в карточке пробела.
              </span>
            )}
            <span className="text-xs text-med-text-muted">{note.length}/1000</span>
          </div>
        </div>

        <div className="mt-4 flex gap-2 rounded-lg border border-med-warning/40 bg-med-warning/10 px-3 py-2.5 text-xs leading-5 text-med-text-primary">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-med-warning" />
          <span>Исходный вопрос и диагностические данные сохранятся</span>
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
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-med-primary px-4 text-sm font-semibold text-white transition-colors hover:bg-med-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            {saving ? 'Сохраняем…' : 'Закрыть пробел'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
