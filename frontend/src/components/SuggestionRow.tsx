import React from 'react';

interface SuggestionRowProps {
  onSelect: (suggestion: string) => void;
}

const suggestions = [
  'Можно ли чистить зубы утром?',
  'Что взять с собой?',
  'Нужен ли сопровождающий?',
];

export const SuggestionRow: React.FC<SuggestionRowProps> = ({ onSelect }) => (
  <div className="px-6 pt-3 bg-white flex flex-wrap items-center gap-2 shrink-0">
    <span className="text-xs text-[#94A3B8]">Возможные уточнения:</span>
    {suggestions.map((suggestion) => (
      <button
        type="button"
        key={suggestion}
        onClick={() => onSelect(suggestion)}
        className="px-3 py-1.5 bg-white border border-[#BFDBFE] rounded-full text-xs text-[#2563EB] font-medium hover:bg-[#EFF6FF] transition-colors"
      >
        {suggestion}
      </button>
    ))}
  </div>
);
