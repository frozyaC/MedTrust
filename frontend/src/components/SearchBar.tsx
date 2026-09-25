import React, { useState } from 'react';
import { Patient } from '../types';
import { Search, UserCheck, AlertCircle, Sparkles, RefreshCw } from 'lucide-react';

interface SearchBarProps {
  selectedPatient: Patient | null;
  onAsk: (query: string) => void;
  onSelectPatientClick: () => void;
  isLoading: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  selectedPatient,
  onAsk,
  onSelectPatientClick,
  isLoading,
}) => {
  const [query, setQuery] = useState('Как подготовиться к гастроскопии?');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onAsk(query);
    }
  };

  const getPatientSummaryText = (p: Patient) => {
    const initials = `${p.name.split(' ')[0]} ${p.name.split(' ')[1]?.[0] || ''}.${p.name.split(' ')[2]?.[0] || ''}.`;
    const allergiesStr = p.allergies.length > 0 ? `, аллергия на ${p.allergies.join(', ')}` : '';
    const contraStr = p.contraindications.length > 0 ? `, ${p.contraindications.join(', ')}` : '';
    return `Пациент: ${initials}, ${p.age} ${p.sex}${allergiesStr}${contraStr}`;
  };

  return (
    <div className="bg-white rounded-xl border border-[#BFDBFE] p-4 shadow-xs space-y-3">
      {/* Patient context banner */}
      <div className="flex items-center justify-between gap-3 text-xs bg-[#EFF6FF] px-3.5 py-2.5 rounded-lg border border-[#DBEAFE]">
        {selectedPatient ? (
          <div className="flex items-center gap-2 text-[#0F172A]">
            <UserCheck className="w-4 h-4 text-[#2563EB] shrink-0" />
            <span className="font-semibold text-[#2563EB]">
              {getPatientSummaryText(selectedPatient)}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-[#475569]">
            <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0" />
            <span>Пациент не выбран — ответ без персонализации</span>
          </div>
        )}

        <button
          type="button"
          onClick={onSelectPatientClick}
          className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] hover:bg-[#DBEAFE] px-2.5 py-1 rounded-md transition-colors shrink-0 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" />
          {selectedPatient ? 'Сменить' : 'Выбрать пациента'}
        </button>
      </div>

      {/* Main search form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите вопрос пациента..."
            className="w-full pl-4 pr-10 py-3 text-sm text-[#0F172A] bg-white border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
          />
          <Sparkles className="w-4 h-4 text-[#3B82F6] absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none opacity-60" />
        </div>

        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="px-6 py-3 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-medium text-sm rounded-lg transition-colors shadow-xs flex items-center gap-2 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Поиск...</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Спросить</span>
            </>
          )}
        </button>
      </form>

      {/* Hint */}
      <p className="text-xs text-[#475569] flex items-center gap-1.5 pl-1">
        <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
        <span>Можно писать обычным языком. Ответ будет персонализирован по выбранному пациенту.</span>
      </p>
    </div>
  );
};
