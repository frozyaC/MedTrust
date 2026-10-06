import React from 'react';

export const AnswerSkeleton: React.FC = () => (
  <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs space-y-6 max-w-[800px] animate-pulse">
    <div className="flex items-center gap-3">
      <div className="w-5 h-5 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
      <span className="font-semibold text-sm text-[#2563EB]">Ищем в базе знаний...</span>
    </div>
    <div className="space-y-3">
      <div className="h-4 bg-[#DBEAFE] rounded w-1/4" />
      <div className="h-3 bg-slate-100 rounded w-full" />
      <div className="h-3 bg-slate-100 rounded w-5/6" />
      <div className="h-4 bg-[#DBEAFE] rounded w-1/3 mt-4" />
      <div className="h-3 bg-slate-100 rounded w-4/5" />
    </div>
  </div>
);
