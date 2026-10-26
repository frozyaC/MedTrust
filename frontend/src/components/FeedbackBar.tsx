import React, { useState } from 'react';
import { ThumbsUp, AlertCircle, Copy, Check, Send, X } from 'lucide-react';
import {
  FEEDBACK_REASONS,
  FeedbackReasonCode,
  getFeedbackReason,
} from '../data/feedbackReasons';

interface FeedbackBarProps {
  onFeedback: (
    type: 'positive' | 'negative' | 'copy',
    reasonCode?: FeedbackReasonCode,
    comment?: string,
  ) => void;
  /** Если передан — тост показывается после отправки (для демо можно не передавать) */
  isSubmitting?: boolean;
}

export const FeedbackBar: React.FC<FeedbackBarProps> = ({ onFeedback, isSubmitting = false }) => {
  const [state, setState] = useState<'idle' | 'choosing' | 'sending' | 'done'>('idle');
  const [selectedReason, setSelectedReason] = useState<FeedbackReasonCode | null>(null);
  const [comment, setComment] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePositive = () => {
    if (state !== 'idle') return;
    setState('sending');
    onFeedback('positive');
    setState('done');
  };

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onFeedback('copy');
  };

  const handleReasonClick = (code: FeedbackReasonCode) => {
    setSelectedReason(code);
    setError(null);
  };

  const handleSubmit = () => {
    if (!selectedReason) return;

    const reason = getFeedbackReason(selectedReason);
    if (!reason) return;

    const trimmed = comment.trim();
    if (reason.requiresComment && !trimmed) {
      setError('Пожалуйста, опишите проблему в комментарии.');
      return;
    }

    setState('sending');
    console.log('sending feedback:', { selectedReason, comment: trimmed });
    onFeedback('negative', selectedReason, trimmed || undefined);
    setState('done');
  };

  const resetPanel = () => {
    setState('idle');
    setSelectedReason(null);
    setComment('');
    setError(null);
  };

  const selectedReasonData = selectedReason ? getFeedbackReason(selectedReason) : null;

  // ── Состояние «Уже отправлено» ──────────────────────────────
  if (state === 'done') {
    return (
      <div className="bg-white rounded-xl border border-[#BFDBFE] p-4 shadow-xs max-w-[800px] mt-4 flex items-center gap-3">
        <Check className="w-5 h-5 text-[#10B981] shrink-0" />
        <span className="text-sm text-[#0F172A]">Спасибо! Отзыв отправлен.</span>
      </div>
    );
  }

  // ── Состояние «Выбор причины» ───────────────────────────────
  if (state === 'choosing' || state === 'sending') {
    return (
      <div className="bg-white rounded-xl border border-[#BFDBFE] p-4 shadow-xs max-w-[800px] mt-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-[#F59E0B]" />
            <span className="text-sm font-semibold text-[#0F172A]">
              Что не так с ответом?
            </span>
          </div>
          <button
            type="button"
            onClick={resetPanel}
            className="text-[#94A3B8] hover:text-[#0F172A] p-1 rounded transition-colors"
            title="Отмена"
            aria-label="Отмена"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="grid gap-1.5">
          {FEEDBACK_REASONS.map((reason) => {
            const active = selectedReason === reason.code;
            return (
              <button
                key={reason.code}
                type="button"
                onClick={() => handleReasonClick(reason.code)}
                className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors ${
                  active
                    ? 'bg-[#EFF6FF] border-[#2563EB] text-[#0F172A]'
                    : 'bg-white border-[#BFDBFE] text-[#475569] hover:bg-[#EFF6FF] hover:border-[#93C5FD]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-3.5 h-3.5 rounded-full border-2 shrink-0 flex items-center justify-center ${
                      active
                        ? 'border-[#2563EB] bg-[#2563EB]'
                        : 'border-[#93C5FD] bg-white'
                    }`}
                  >
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </span>
                  <span className="font-semibold">{reason.label}</span>
                  {reason.createsGap && (
                    <span className="ml-auto text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#92400E]">
                      Пробел
                    </span>
                  )}
                </div>
                {reason.description && (
                  <p className="ml-5.5 mt-0.5 text-[11px] text-[#94A3B8]">{reason.description}</p>
                )}
              </button>
            );
          })}
        </div>

        {selectedReasonData && (
          <div className="space-y-1">
            <label
              htmlFor="feedback-comment"
              className="text-xs font-semibold text-[#0F172A]"
            >
              Комментарий{' '}
              {selectedReasonData.requiresComment ? (
                <span className="text-[#EF4444]">*</span>
              ) : (
                <span className="text-[#94A3B8] font-normal">(необязательно)</span>
              )}
            </label>
            <textarea
              id="feedback-comment"
              value={comment}
              onChange={(e) => {
                setComment(e.target.value);
                if (error) setError(null);
              }}
              rows={2}
              maxLength={1000}
              placeholder={
                selectedReasonData.requiresComment
                  ? 'Опишите, что не так'
                  : 'Можете добавить пояснение'
              }
              className="w-full px-3 py-2 text-xs text-[#0F172A] bg-white border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8] resize-y"
            />
            <div className="flex items-center justify-between">
              {error ? (
                <p className="text-[11px] text-[#EF4444]">{error}</p>
              ) : selectedReasonData.recommendsComment && !selectedReasonData.requiresComment ? (
                <p className="text-[11px] text-[#94A3B8]">Комментарий поможет разобраться</p>
              ) : (
                <span />
              )}
              <span className="text-[11px] text-[#94A3B8]">{comment.length}/1000</span>
            </div>
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={resetPanel}
            disabled={state === 'sending'}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#BFDBFE] bg-white text-[#475569] hover:bg-[#EFF6FF] transition-colors disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!selectedReason || state === 'sending'}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            <Send className="w-3.5 h-3.5" />
            {state === 'sending' ? 'Отправка...' : 'Отправить'}
          </button>
        </div>
      </div>
    );
  }

  // ── Обычное состояние — 3 кнопки ─────────────────────────────
  return (
    <div className="bg-white rounded-xl border border-[#BFDBFE] p-4 shadow-xs max-w-[800px] mt-4 flex flex-wrap items-center justify-between gap-3">
      <span className="text-sm font-semibold text-[#0F172A]">Ответ полезен?</span>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={handlePositive}
          disabled={isSubmitting}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border bg-white text-[#475569] border-[#BFDBFE] hover:bg-[#EFF6FF] hover:border-[#93C5FD] disabled:opacity-50"
        >
          <ThumbsUp className="w-3.5 h-3.5" />
          <span>Полезно</span>
        </button>

        <button
          type="button"
          onClick={() => setState('choosing')}
          disabled={isSubmitting}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border bg-white text-[#475569] border-[#BFDBFE] hover:bg-amber-50 hover:border-amber-200 disabled:opacity-50"
        >
          <AlertCircle className="w-3.5 h-3.5" />
          <span>Проблема с ответом</span>
        </button>

        <div className="h-4 w-[1px] bg-[#BFDBFE] mx-1 hidden sm:block" />

        <button
          type="button"
          onClick={handleCopy}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#475569] border border-[#BFDBFE] hover:bg-[#EFF6FF] hover:border-[#93C5FD] transition-all flex items-center gap-1.5"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-[#10B981]" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
          <span>{copied ? 'Скопировано' : 'Скопировать'}</span>
        </button>
      </div>
    </div>
  );
};