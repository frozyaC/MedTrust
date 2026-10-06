import React from 'react';

export const SessionDivider: React.FC = () => (
  <div className="flex items-center gap-3 max-w-[800px]">
    <div className="h-px bg-[#BFDBFE] flex-1" />
    <span className="px-3 py-1 bg-white border border-[#DBEAFE] rounded-full text-xs text-[#94A3B8]">
      Сегодня
    </span>
    <div className="h-px bg-[#BFDBFE] flex-1" />
  </div>
);
