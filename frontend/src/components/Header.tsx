import React from 'react';
import { HelpCircle, Stethoscope, BookOpen } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="h-[64px] bg-white border-b border-[#BFDBFE] px-6 flex items-center justify-between shrink-0 select-none z-10 shadow-xs">
      {/* Left section: Logo & Clinic Name & Status Chips */}
      <div className="flex items-center gap-6">
        {/* MedTrust Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-[#2563EB] flex items-center justify-center text-white shadow-sm">
            <Stethoscope className="w-5 h-5" />
          </div>
          <span className="font-bold text-xl text-[#0F172A] tracking-tight">MedTrust</span>
        </div>

        {/* Divider */}
        <div className="h-5 w-[1px] bg-[#BFDBFE]" />

        {/* Clinic name */}
        <span className="text-sm font-semibold text-[#0F172A]">ГКБ № 12</span>

        {/* Status Chips */}
        <div className="flex items-center gap-2">
          {/* CRM status */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse" />
            <span>CRM: подключена</span>
          </div>

          {/* wiki.js status */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#DBEAFE] text-[#1D4ED8] border border-[#93C5FD]">
            <BookOpen className="w-3.5 h-3.5 text-[#2563EB]" />
            <span>wiki.js: 12 430 статей</span>
          </div>
        </div>
      </div>

      {/* Right section: Role, Name, Help, Avatar */}
      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="text-xs text-[#94A3B8] font-medium">Регистратор</div>
          <div className="text-sm font-semibold text-[#0F172A]">Иванова М.А.</div>
        </div>

        <button 
          className="p-1.5 text-[#475569] hover:text-[#2563EB] hover:bg-[#EFF6FF] rounded-lg transition-colors"
          title="Справка и поддержка"
        >
          <HelpCircle className="w-5 h-5" />
        </button>

        {/* User avatar */}
        <div className="w-9 h-9 rounded-full bg-[#DBEAFE] border-2 border-[#93C5FD] flex items-center justify-center text-[#2563EB] font-bold text-sm shadow-xs">
          ИМ
        </div>
      </div>
    </header>
  );
};
