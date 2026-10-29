import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, X } from 'lucide-react';

type BannerState = 'idle' | 'cancelling' | 'cancelled' | 'error';

interface GapBannerProps {
  /** id записи в knowledge_gaps — нужен для PATCH при отмене */
  gapId: string | number;
  /** 'automatic' (автопробел из /query) или 'user_feedback' (из фидбека) */
  source?: 'automatic' | 'user_feedback';
  /** Вызывается по клику «Отменить». Должен бросить ошибку при неудаче. */
  onCancel: (gapId: string | number) => Promise<void>;
}

/**
 * Плашка «Пробел в БЗ зафиксирован» под ответом.
 */
export const GapBanner: React.FC<GapBannerProps> = ({ gapId, source = 'automatic', onCancel }) => {
  const [state, setState] = useState<BannerState>('idle');
  const [errorText, setErrorText] = useState<string | null>(null);

  const handleCancel = async () => {
    if (state === 'cancelling' || state === 'cancelled') return;
    setState('cancelling');
    setErrorText(null);
    try {
      await onCancel(gapId);
      setState('cancelled');
    } catch (error) {
      setState('error');
      setErrorText(
        error instanceof Error && error.message
          ? error.message
          : 'Не удалось отменить пробел',
      );
    }
  };

  if (state === 'cancelled') {
    return (
      <div className="max-w-[800px] rounded-xl border border-[#BFDBFE] bg-white px-4 py-3 shadow-xs flex items-center gap-2.5">
        <CheckCircle2 className="w-4 h-4 text-[#10B981] shrink-0" />
        <span className="text-xs text-[#0F172A]">
          Пробел отменён. Запись останется в истории админки со статусом «Отклонён».
        </span>
      </div>
    );
  }

  const isAutomatic = source === 'automatic';

  return (
    <div className="max-w-[800px] rounded-xl border border-[#FDE68A] bg-[#FFFBEB] px-4 py-3 shadow-xs">
      <div className="flex items-start gap-2.5">
        <Info className="w-4 h-4 text-[#B45309] shrink-0 mt-0.5" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[#B45309]">
            {isAutomatic
              ? 'Пробел в базе знаний зафиксирован автоматически'
              : 'Пробел в базе знаний зафиксирован по вашему отзыву'}
          </p>
          <p className="mt-0.5 text-xs leading-5 text-[#92400E]">
            {isAutomatic
              ? 'Ответ не покрыт корпоративной базой знаний. Заведующий регистратурой увидит запись в «Карте пробелов».'
              : 'Заведующий регистратурой увидит запись в «Карте пробелов» вместе с вашим комментарием.'}
          </p>

          {state === 'error' && errorText && (
            <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-[#EF4444]">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {errorText}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {state === 'error' ? (
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-lg border border-[#FDE68A] bg-white px-2.5 py-1 text-xs font-semibold text-[#B45309] transition-colors hover:bg-[#FEF3C7]"
            >
              Повторить
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCancel}
              disabled={state === 'cancelling'}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#FDE68A] bg-white px-2.5 py-1 text-xs font-semibold text-[#B45309] transition-colors hover:bg-[#FEF3C7] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {state === 'cancelling' ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Отменяем…
                </>
              ) : (
                <>
                  <X className="w-3.5 h-3.5" />
                  Отменить
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};