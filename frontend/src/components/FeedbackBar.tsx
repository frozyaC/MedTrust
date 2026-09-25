import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, HelpCircle, Copy, Check } from 'lucide-react';

interface FeedbackBarProps {
  onFeedback: (type: 'useful' | 'useless' | 'not_found' | 'copy') => void;
}

export const FeedbackBar: React.FC<FeedbackBarProps> = ({ onFeedback }) => {
  const [selected, setSelected] = useState<'useful' | 'useless' | 'not_found' | null>(null);
  const [copied, setCopied] = useState(false);

  const handleAction = (type: 'useful' | 'useless' | 'not_found' | 'copy') => {
    if (type === 'copy') {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onFeedback('copy');
      return;
    }
    setSelected(type);
    onFeedback(type);
  };

  return (
    <div className="bg-white rounded-xl border border-[#BFDBFE] p-4 shadow-xs max-w-[800px] mt-4 flex flex-wrap items-center justify-between gap-3">
      <span className="text-sm font-semibold text-[#0F172A] flex items-center gap-2">
        <span>Ответ полезен?</span>
      </span>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => handleAction('useful')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
            selected === 'useful'
              ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-xs'
              : 'bg-white text-[#475569] border-[#BFDBFE] hover:bg-[#EFF6FF] hover:border-[#93C5FD]'
          }`}
        >
          <ThumbsUp className="w-3.5 h-3.5" />
          <span>Полезно</span>
        </button>

        <button
          onClick={() => handleAction('useless')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
            selected === 'useless'
              ? 'bg-[#EF4444] text-white border-[#EF4444] shadow-xs'
              : 'bg-white text-[#475569] border-[#BFDBFE] hover:bg-red-50 hover:border-red-200'
          }`}
        >
          <ThumbsDown className="w-3.5 h-3.5" />
          <span>Бесполезно</span>
        </button>

        <button
          onClick={() => handleAction('not_found')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
            selected === 'not_found'
              ? 'bg-[#F59E0B] text-white border-[#F59E0B] shadow-xs'
              : 'bg-white text-[#475569] border-[#BFDBFE] hover:bg-amber-50 hover:border-amber-200'
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Ответ не найден</span>
        </button>

        <div className="h-4 w-[1px] bg-[#BFDBFE] mx-1 hidden sm:block" />

        <button
          onClick={() => handleAction('copy')}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#475569] border border-[#BFDBFE] hover:bg-[#EFF6FF] hover:border-[#93C5FD] transition-all flex items-center gap-1.5"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Скопировано' : 'Скопировать'}</span>
        </button>
      </div>
    </div>
  );
};
