import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Pencil, Plus, RotateCcw, Trash2, X } from 'lucide-react';
import {
  MAX_SUGGESTIONS,
  SuggestionQuestion,
  SuggestionQuestionsConfig,
} from '../types/suggestionQuestions';
import {
  DEFAULT_SUGGESTIONS,
  createSuggestionId,
} from '../data/suggestionQuestions';
import { lockBodyScroll } from '../lib/scrollLock';

interface SuggestionEditorProps {
  config: SuggestionQuestionsConfig;
  onSave: (config: SuggestionQuestionsConfig) => void;
  onClose: () => void;
}

/**
 * Модалка «Возможные уточнения»: плоский список вопросов.
 */
export const SuggestionEditor: React.FC<SuggestionEditorProps> = ({
  config,
  onSave,
  onClose,
}) => {
  const [draft, setDraft] = useState<SuggestionQuestionsConfig>(() =>
    structuredClone(config),
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newQuestion, setNewQuestion] = useState('');
  const newInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => lockBodyScroll(), []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const isFull = draft.suggestions.length >= MAX_SUGGESTIONS;
  const canAdd = !isFull && newQuestion.trim().length > 0;

  const handleAdd = () => {
    const value = newQuestion.trim();
    if (!value || isFull) return;
    const item: SuggestionQuestion = { id: createSuggestionId(), label: value };
    setDraft((prev) => ({
      ...prev,
      suggestions: [...prev.suggestions, item],
    }));
    setNewQuestion('');
    setEditingId(item.id);
  };

  const handleUpdate = (id: string, label: string) => {
    const value = label.trim();
    setDraft((prev) => ({
      ...prev,
      suggestions: prev.suggestions.map((s) =>
        s.id === id ? { ...s, label: value } : s,
      ),
    }));
    setEditingId(null);
  };

  const handleDelete = (id: string) => {
    setDraft((prev) => ({
      ...prev,
      suggestions: prev.suggestions.filter((s) => s.id !== id),
    }));
    if (editingId === id) setEditingId(null);
  };

  const handleReset = () => {
    if (!window.confirm('Сбросить уточняющие вопросы к начальному списку?')) {
      return;
    }
    setDraft(structuredClone(DEFAULT_SUGGESTIONS));
    setEditingId(null);
    setNewQuestion('');
  };

  const handleSave = () => {
    // Сохраняем только непустые вопросы (защита от пустых label)
    const cleaned: SuggestionQuestion[] = draft.suggestions
      .map((s) => ({ ...s, label: s.label.trim() }))
      .filter((s) => s.label.length > 0);
    onSave({ version: 1, suggestions: cleaned });
    onClose();
  };

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-[#0F172A]/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="suggestion-editor-title"
        className="relative flex max-h-[90vh] w-full max-w-[560px] flex-col overflow-hidden rounded-xl border border-[#BFDBFE] bg-white shadow-2xl"
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-[#DBEAFE] px-6 py-4">
          <div>
            <h2
              id="suggestion-editor-title"
              className="text-lg font-semibold text-[#0F172A]"
            >
              Редактор уточняющих вопросов
            </h2>
            <p className="mt-0.5 text-xs text-[#475569]">
              {draft.suggestions.length} из {MAX_SUGGESTIONS} · вопросы появятся над полем ввода
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#475569] transition-colors hover:bg-[#EFF6FF] hover:text-[#0F172A]"
            aria-label="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-6 py-4">
          {draft.suggestions.length === 0 && (
            <div className="rounded-lg border border-dashed border-[#BFDBFE] bg-[#EFF6FF] px-3 py-6 text-center text-sm text-[#94A3B8]">
              Нет уточняющих вопросов. Добавьте первый.
            </div>
          )}

          {draft.suggestions.map((item, index) => {
            const isEditing = editingId === item.id;
            return (
              <div
                key={item.id}
                className="flex items-center gap-2 rounded-lg border border-[#DBEAFE] bg-white px-2.5 py-1.5"
              >
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide text-[#94A3B8] w-6 text-center">
                  {index + 1}
                </span>
                {isEditing ? (
                  <>
                    <input
                      type="text"
                      defaultValue={item.label}
                      autoFocus
                      maxLength={120}
                      onBlur={(event) => handleUpdate(item.id, event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          handleUpdate(item.id, event.currentTarget.value);
                        }
                        if (event.key === 'Escape') setEditingId(null);
                      }}
                      className="flex-1 rounded-md border border-[#3B82F6] px-2 py-1 text-sm text-[#0F172A] focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="shrink-0 rounded p-1 text-[#10B981] transition-colors hover:bg-[#EFF6FF]"
                      aria-label="Готово"
                      title="Готово"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  </>
                ) : (
                  <>
                    <span
                      className="min-w-0 flex-1 truncate text-sm text-[#0F172A]"
                      title={item.label}
                    >
                      {item.label || <span className="text-[#94A3B8]">(без названия)</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() => setEditingId(item.id)}
                      className="shrink-0 rounded p-1 text-[#475569] transition-colors hover:bg-[#EFF6FF] hover:text-[#2563EB]"
                      title="Редактировать"
                      aria-label="Редактировать"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(item.id)}
                      className="shrink-0 rounded p-1 text-[#475569] transition-colors hover:bg-red-50 hover:text-[#EF4444]"
                      title="Удалить"
                      aria-label="Удалить"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </>
                )}
              </div>
            );
          })}

          {/* Add new */}
          <div className="mt-3 flex items-center gap-2 border-t border-[#DBEAFE] pt-3">
            <input
              ref={newInputRef}
              type="text"
              value={newQuestion}
              onChange={(event) => setNewQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handleAdd();
              }}
              maxLength={120}
              disabled={isFull}
              placeholder={
                isFull
                  ? `Достигнут лимит (${MAX_SUGGESTIONS})`
                  : 'Новый уточняющий вопрос'
              }
              className="flex-1 rounded-lg border border-[#BFDBFE] px-3 py-2 text-sm text-[#0F172A] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#3B82F6] disabled:cursor-not-allowed disabled:bg-[#F8FBFF] disabled:text-[#94A3B8]"
            />
            <button
              type="button"
              onClick={handleAdd}
              disabled={!canAdd}
              className="flex shrink-0 items-center gap-1 rounded-lg border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-2 text-xs font-semibold text-[#2563EB] transition-colors hover:bg-[#DBEAFE] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              Добавить
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-[#DBEAFE] px-6 py-4">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center gap-1 text-xs font-medium text-[#94A3B8] transition-colors hover:text-[#EF4444]"
            title="Сбросить к начальному списку"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Сбросить
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#BFDBFE] bg-white px-4 py-2 text-sm font-semibold text-[#475569] transition-colors hover:bg-[#EFF6FF]"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="rounded-lg bg-[#2563EB] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#1D4ED8]"
            >
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
};