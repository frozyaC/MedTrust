import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  ArrowRightLeft,
  RotateCcw,
} from 'lucide-react';
import {
  PopularQuestionsConfig,
  PopularQuestionCategory,
  PopularQuestionPreset,
} from '../types/popularQuestions';
import { DEFAULT_POPULAR_QUESTIONS } from '../data/popularQuestions';

interface PopularQuestionsEditorProps {
  config: PopularQuestionsConfig;
  onSave: (config: PopularQuestionsConfig) => void;
  onClose: () => void;
}

function uid(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const PopularQuestionsEditor: React.FC<PopularQuestionsEditorProps> = ({
  config,
  onSave,
  onClose,
}) => {
  const [draft, setDraft] = useState<PopularQuestionsConfig>(() =>
    structuredClone(config),
  );
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editingPresetId, setEditingPresetId] = useState<string | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [addingPresetTo, setAddingPresetTo] = useState<string | null>(null);
  const [movingPreset, setMovingPreset] = useState<{
    fromCategoryId: string;
    presetId: string;
  } | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set(),
  );

  const toggleCollapse = (categoryId: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(categoryId)) next.delete(categoryId);
      else next.add(categoryId);
      return next;
    });
  };

  const updateCategory = (
    categoryId: string,
    updater: (cat: PopularQuestionCategory) => PopularQuestionCategory,
  ) => {
    setDraft((prev) => ({
      ...prev,
      categories: prev.categories.map((c) => (c.id === categoryId ? updater(c) : c)),
    }));
  };

  const handleAddCategory = () => {
    const name = newCategoryName.trim();
    if (!name) return;
    setDraft((prev) => ({
      ...prev,
      categories: [
        ...prev.categories,
        { id: uid('cat'), name, presets: [] },
      ],
    }));
    setNewCategoryName('');
  };

  const handleDeleteCategory = (categoryId: string) => {
    setDraft((prev) => ({
      ...prev,
      categories: prev.categories.filter((c) => c.id !== categoryId),
    }));
  };

  const handleRenameCategory = (categoryId: string, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    updateCategory(categoryId, (cat) => ({ ...cat, name: trimmed }));
    setEditingCategoryId(null);
  };

  const handleAddPreset = (categoryId: string) => {
    const label = 'Новый вопрос...';
    const value = 'Новый вопрос ';
    updateCategory(categoryId, (cat) => ({
      ...cat,
      presets: [...cat.presets, { id: uid('p'), label, value }],
    }));
    setAddingPresetTo(null);
    setEditingPresetId(null);
  };

  const handleUpdatePreset = (
    categoryId: string,
    presetId: string,
    patch: Partial<Pick<PopularQuestionPreset, 'label' | 'value'>>,
  ) => {
    updateCategory(categoryId, (cat) => ({
      ...cat,
      presets: cat.presets.map((p) => (p.id === presetId ? { ...p, ...patch } : p)),
    }));
  };

  const handleDeletePreset = (categoryId: string, presetId: string) => {
    updateCategory(categoryId, (cat) => ({
      ...cat,
      presets: cat.presets.filter((p) => p.id !== presetId),
    }));
  };

  const handleMovePreset = (toCategoryId: string) => {
    if (!movingPreset) return;
    const { fromCategoryId, presetId } = movingPreset;
    if (fromCategoryId === toCategoryId) {
      setMovingPreset(null);
      return;
    }

    const from = draft.categories.find((c) => c.id === fromCategoryId);
    const preset = from?.presets.find((p) => p.id === presetId);
    if (!preset) return;

    setDraft((prev) => ({
      ...prev,
      categories: prev.categories.map((c) => {
        if (c.id === fromCategoryId) {
          return { ...c, presets: c.presets.filter((p) => p.id !== presetId) };
        }
        if (c.id === toCategoryId) {
          return { ...c, presets: [...c.presets, preset] };
        }
        return c;
      }),
    }));
    setMovingPreset(null);
  };

  const handleSave = () => {
    onSave(draft);
    onClose();
  };

  const handleResetToDefaults = () => {
    if (!window.confirm('Сбросить все популярные вопросы к заводским настройкам?')) {
      return;
    }
    setDraft(structuredClone(DEFAULT_POPULAR_QUESTIONS));
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
        aria-labelledby="pq-editor-title"
        className="relative w-full max-w-[720px] max-h-[90vh] bg-white rounded-xl border border-[#BFDBFE] shadow-2xl flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#DBEAFE] shrink-0">
          <div>
            <h2
              id="pq-editor-title"
              className="text-lg font-semibold text-[#0F172A]"
            >
              Редактор популярных вопросов
            </h2>
            <p className="text-xs text-[#475569] mt-0.5">
              Настройте категории и заготовки под свою работу
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#475569] hover:bg-[#EFF6FF] hover:text-[#0F172A] transition-colors"
            aria-label="Закрыть"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {draft.categories.length === 0 && (
            <div className="text-center py-8 text-sm text-[#94A3B8]">
              Нет категорий. Добавьте первую.
            </div>
          )}

          {draft.categories.map((cat) => {
            const collapsed = collapsedCategories.has(cat.id);
            const isEditingCat = editingCategoryId === cat.id;

            return (
              <div
                key={cat.id}
                className="rounded-lg border border-[#DBEAFE] bg-[#F8FBFF]"
              >
                {/* Category header */}
                <div className="flex items-center gap-2 px-3 py-2 border-b border-[#DBEAFE]">
                  <button
                    type="button"
                    onClick={() => toggleCollapse(cat.id)}
                    className="p-0.5 text-[#475569] hover:text-[#0F172A]"
                    aria-label={collapsed ? 'Развернуть' : 'Свернуть'}
                  >
                    {collapsed ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronUp className="w-4 h-4" />
                    )}
                  </button>

                  {isEditingCat ? (
                    <input
                      type="text"
                      defaultValue={cat.name}
                      autoFocus
                      onBlur={(e) => handleRenameCategory(cat.id, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleRenameCategory(cat.id, e.currentTarget.value);
                        }
                        if (e.key === 'Escape') setEditingCategoryId(null);
                      }}
                      className="flex-1 px-2 py-1 text-sm font-semibold text-[#0F172A] border border-[#3B82F6] rounded-md focus:outline-none"
                    />
                  ) : (
                    <span className="flex-1 text-sm font-semibold text-[#0F172A]">
                      {cat.name}
                      <span className="ml-2 text-xs font-normal text-[#94A3B8]">
                        ({cat.presets.length})
                      </span>
                    </span>
                  )}

                  <button
                    type="button"
                    onClick={() => setEditingCategoryId(cat.id)}
                    className="p-1 text-[#475569] hover:text-[#2563EB] hover:bg-white rounded transition-colors"
                    title="Переименовать категорию"
                    aria-label="Переименовать"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteCategory(cat.id)}
                    className="p-1 text-[#475569] hover:text-[#EF4444] hover:bg-white rounded transition-colors"
                    title="Удалить категорию"
                    aria-label="Удалить"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Presets */}
                {!collapsed && (
                  <div className="p-3 space-y-1.5">
                    {cat.presets.length === 0 && (
                      <p className="text-xs text-[#94A3B8] py-1">
                        Нет заготовок в этой категории
                      </p>
                    )}

                    {cat.presets.map((preset) => {
                      const isEditing = editingPresetId === preset.id;
                      const isMoving =
                        movingPreset?.fromCategoryId === cat.id &&
                        movingPreset.presetId === preset.id;

                      return (
                        <div
                          key={preset.id}
                          className={`rounded-md border bg-white px-2 py-1.5 ${
                            isMoving
                              ? 'border-[#F59E0B] ring-2 ring-[#F59E0B]/30'
                              : 'border-[#DBEAFE]'
                          }`}
                        >
                          {isEditing ? (
                            <div className="space-y-1">
                              <div className="flex items-center gap-1.5">
                                <span className="text-[10px] uppercase font-bold text-[#94A3B8] w-[48px] shrink-0">
                                  Кнопка
                                </span>
                                <input
                                  type="text"
                                  defaultValue={preset.label}
                                  autoFocus
                                  onBlur={(e) =>
                                    handleUpdatePreset(cat.id, preset.id, {
                                      label: e.target.value,
                                    })
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      handleUpdatePreset(cat.id, preset.id, {
                                        label: e.currentTarget.value,
                                      });
                                      setEditingPresetId(null);
                                    }
                                    if (e.key === 'Escape') setEditingPresetId(null);
                                  }}
                                  className="flex-1 px-2 py-1 text-xs border border-[#BFDBFE] rounded focus:outline-none focus:border-[#3B82F6]"
                                />
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-[10px] uppercase font-bold text-[#94A3B8] w-[48px] shrink-0">
                                  Текст
                                </span>
                                <input
                                  type="text"
                                  defaultValue={preset.value}
                                  onBlur={(e) =>
                                    handleUpdatePreset(cat.id, preset.id, {
                                      value: e.target.value,
                                    })
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      handleUpdatePreset(cat.id, preset.id, {
                                        value: e.currentTarget.value,
                                      });
                                      setEditingPresetId(null);
                                    }
                                    if (e.key === 'Escape') setEditingPresetId(null);
                                  }}
                                  className="flex-1 px-2 py-1 text-xs border border-[#BFDBFE] rounded focus:outline-none focus:border-[#3B82F6]"
                                />
                                <button
                                  type="button"
                                  onClick={() => setEditingPresetId(null)}
                                  className="p-1 text-[#10B981] hover:bg-[#EFF6FF] rounded"
                                  aria-label="Готово"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-[#0F172A] truncate">
                                  {preset.label}
                                </div>
                                <div className="text-[10px] text-[#94A3B8] truncate font-mono">
                                  → «{preset.value}»
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => setEditingPresetId(preset.id)}
                                className="p-1 text-[#475569] hover:text-[#2563EB] hover:bg-[#EFF6FF] rounded transition-colors"
                                title="Редактировать"
                                aria-label="Редактировать"
                              >
                                <Pencil className="w-3 h-3" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setMovingPreset({
                                    fromCategoryId: cat.id,
                                    presetId: preset.id,
                                  })
                                }
                                className="p-1 text-[#475569] hover:text-[#F59E0B] hover:bg-amber-50 rounded transition-colors"
                                title="Переместить в другую категорию"
                                aria-label="Переместить"
                              >
                                <ArrowRightLeft className="w-3 h-3" />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeletePreset(cat.id, preset.id)}
                                className="p-1 text-[#475569] hover:text-[#EF4444] hover:bg-red-50 rounded transition-colors"
                                title="Удалить"
                                aria-label="Удалить"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}

                    <button
                      type="button"
                      onClick={() => handleAddPreset(cat.id)}
                      className="w-full py-1.5 text-xs font-medium text-[#2563EB] border border-dashed border-[#93C5FD] rounded-md hover:bg-[#EFF6FF] transition-colors flex items-center justify-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Добавить заготовку
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {/* Add category */}
          <div className="flex items-center gap-2 pt-2 border-t border-[#DBEAFE]">
            <input
              type="text"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddCategory();
              }}
              placeholder="Название новой категории"
              className="flex-1 px-3 py-2 text-sm border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent"
            />
            <button
              type="button"
              onClick={handleAddCategory}
              disabled={!newCategoryName.trim()}
              className="px-3 py-2 text-xs font-semibold bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE] rounded-lg hover:bg-[#DBEAFE] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" />
              Добавить категорию
            </button>
          </div>
        </div>

        {/* Move preset dialog */}
        {movingPreset && (
          <div className="px-6 py-3 border-t border-[#FDE68A] bg-[#FFFBEB] flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-[#B45309]">
              Переместить в:
            </span>
            {draft.categories
              .filter((c) => c.id !== movingPreset.fromCategoryId)
              .map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => handleMovePreset(c.id)}
                  className="px-2.5 py-1 text-xs font-medium bg-white border border-[#FDE68A] rounded-md hover:bg-[#FEF3C7] transition-colors"
                >
                  {c.name}
                </button>
              ))}
            <button
              type="button"
              onClick={() => setMovingPreset(null)}
              className="ml-auto px-2 py-1 text-xs text-[#B45309] hover:underline"
            >
              Отмена
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#DBEAFE] flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={handleResetToDefaults}
            className="text-xs font-medium text-[#94A3B8] hover:text-[#EF4444] transition-colors flex items-center gap-1"
            title="Сбросить к заводским настройкам"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Сбросить
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-semibold text-[#475569] bg-white border border-[#BFDBFE] rounded-lg hover:bg-[#EFF6FF] transition-colors"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 text-sm font-semibold text-white bg-[#2563EB] rounded-lg hover:bg-[#1D4ED8] transition-colors shadow-sm"
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