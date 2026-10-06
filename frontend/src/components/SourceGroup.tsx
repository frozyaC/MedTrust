import React from 'react';
import { AnswerData } from '../types';
import { SourceCard } from './SourceCard';
import { BookOpen, ChevronDown } from 'lucide-react';

interface SourceGroupProps {
  answer: AnswerData;
  answerId: string;
  expanded: boolean;
  highlightedId: number | null;
  onToggle: () => void;
}

export const SourceGroup: React.FC<SourceGroupProps> = ({
  answer,
  answerId,
  expanded,
  highlightedId,
  onToggle,
}) => (
  <div className="max-w-[800px]">
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-2 text-sm font-semibold text-[#0F172A] hover:text-[#2563EB] transition-colors"
      aria-expanded={expanded}
    >
      <BookOpen className="w-5 h-5 text-[#2563EB]" />
      <span>Источники ({answer.sources.length})</span>
      <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
    </button>
    {expanded && (
      <SourceCard
        sources={answer.sources}
        highlightedId={highlightedId}
        idPrefix={`source-${answerId}`}
        showHeader={false}
      />
    )}
  </div>
);
