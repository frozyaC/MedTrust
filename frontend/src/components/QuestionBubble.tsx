import React from 'react';
import { User } from 'lucide-react';

interface QuestionBubbleProps {
  text: string;
  time: string;
}

export const QuestionBubble: React.FC<QuestionBubbleProps> = ({ text, time }) => (
  <div className="flex flex-col items-end max-w-[800px]">
    <div className="max-w-[640px] bg-[#2563EB] text-white px-4 py-3 rounded-xl rounded-tr-sm shadow-xs text-sm font-medium">
      {text}
    </div>
    <div className="text-[11px] text-[#94A3B8] mt-1.5 flex items-center gap-1.5 px-1">
      <User className="w-3 h-3" />
      <span>Регистратор, {time}</span>
    </div>
  </div>
);
