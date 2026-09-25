import React, { useState } from 'react';
import { Patient } from '../types';
import { PatientCard } from './PatientCard';
import { Search, Users, X } from 'lucide-react';

interface SidebarProps {
  patients: Patient[];
  selectedPatient: Patient | null;
  onSelectPatient: (patient: Patient | null) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  patients,
  selectedPatient,
  onSelectPatient,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'today' | 'my' | 'all'>('all');

  const filteredPatients = patients.filter((p) => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return true;
    return (
      p.name.toLowerCase().includes(query) ||
      p.allergies.some((a) => a.toLowerCase().includes(query)) ||
      p.chronic.some((c) => c.toLowerCase().includes(query)) ||
      p.contraindications.some((ci) => ci.toLowerCase().includes(query))
    );
  });

  return (
    <aside className="w-[320px] bg-[#F0F7FF] border-r border-[#BFDBFE] flex flex-col shrink-0 h-[calc(100vh-64px)]">
      {/* Top Header */}
      <div className="p-4 border-b border-[#BFDBFE] bg-white/50 backdrop-blur-xs">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-[#2563EB]" />
            <h2 className="font-semibold text-lg text-[#0F172A]">Пациенты</h2>
          </div>
          {selectedPatient && (
            <button
              onClick={() => onSelectPatient(null)}
              className="text-xs text-[#2563EB] hover:underline font-medium flex items-center gap-1"
              title="Снять выбор"
            >
              <X className="w-3.5 h-3.5" />
              Сбросить
            </button>
          )}
        </div>

        {/* Search input */}
        <div className="relative mb-3">
          <Search className="w-4 h-4 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по ФИО, телефону или карте"
            className="w-[100%] pl-9 pr-3 py-2 bg-white text-xs text-[#0F172A] border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#0F172A]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter chips */}
        <div className="flex gap-1.5 p-0.5 bg-[#DBEAFE]/50 rounded-lg text-xs font-medium">
          <button
            onClick={() => setFilter('today')}
            className={`flex-1 py-1 px-2 rounded-md transition-all ${
              filter === 'today'
                ? 'bg-white text-[#2563EB] shadow-xs font-semibold'
                : 'text-[#475569] hover:text-[#0F172A]'
            }`}
          >
            Сегодня
          </button>
          <button
            onClick={() => setFilter('my')}
            className={`flex-1 py-1 px-2 rounded-md transition-all ${
              filter === 'my'
                ? 'bg-white text-[#2563EB] shadow-xs font-semibold'
                : 'text-[#475569] hover:text-[#0F172A]'
            }`}
          >
            Мои
          </button>
          <button
            onClick={() => setFilter('all')}
            className={`flex-1 py-1 px-2 rounded-md transition-all ${
              filter === 'all'
                ? 'bg-white text-[#2563EB] shadow-xs font-semibold'
                : 'text-[#475569] hover:text-[#0F172A]'
            }`}
          >
            Все ({patients.length})
          </button>
        </div>
      </div>

      {/* Patient Cards List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredPatients.length > 0 ? (
          filteredPatients.map((patient) => (
            <PatientCard
              key={patient.id}
              patient={patient}
              isSelected={selectedPatient?.id === patient.id}
              onSelect={(p) => onSelectPatient(selectedPatient?.id === p.id ? null : p)}
            />
          ))
        ) : (
          <div className="text-center py-8 px-4 text-[#475569]">
            <p className="text-sm font-medium">Пациенты не найдены</p>
            <p className="text-xs text-[#94A3B8] mt-1">Попробуйте изменить запрос</p>
          </div>
        )}
      </div>
    </aside>
  );
};
