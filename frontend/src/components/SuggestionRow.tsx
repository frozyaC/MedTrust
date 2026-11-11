import React from 'react';
import { Pencil } from 'lucide-react';
import { SuggestionQuestion } from '../types/suggestionQuestions';

interface SuggestionRowProps {
  suggestions: SuggestionQuestion[];
  onSelect: (suggestion: string) => void;
  onEdit: () => void;
}

export const SuggestionRow: React.FC<SuggestionRowProps> = ({
  suggestions,
  onSelect,
  onEdit,
}) => (
  <div className="flex flex-wrap items-center gap-2 bg-white px-6 pt-3 shrink-0">
    <span className="text-xs text-[#94A3B8]">Возможные уточнения:</span>
    {suggestions.map((item) => (
      <button
        type="button"
        key={item.id}
        onClick={() => onSelect(item.label)}
        className="rounded-full border border-[#BFDBFE] bg-white px-3 py-1.5 text-xs font-medium text-[#2563EB] transition-colors hover:bg-[#EFF6FF]"
      >
        {item.label}
      </button>
    ))}
    {suggestions.length === 0 && (
      <span className="text-xs text-[#94A3B8]">(нет уточняющих вопросов)</span>
    )}
    <button
      type="button"
      onClick={onEdit}
      className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-[#475569] transition-colors hover:bg-[#EFF6FF] hover:text-[#2563EB]"
      title="Редактировать уточняющие вопросы"
    >
      <Pencil className="h-3.5 w-3.5" />
      Редактировать
    </button>
  </div>
);