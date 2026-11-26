import React, { useId, useLayoutEffect, useRef, useState } from 'react';
import { Patient } from '../types';
import { PatientCard } from './PatientCard';
import { Search, Users, X } from 'lucide-react';

interface SidebarProps {
  patients: Patient[];
  selectedPatient: Patient | null;
  onSelectPatient: (patient: Patient | null) => void;
  searchInputRef?: React.RefObject<HTMLInputElement | null>;
  highlighted?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  patients,
  selectedPatient,
  onSelectPatient,
  searchInputRef,
  highlighted = false,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'today' | 'my' | 'all'>('all');
  const [activePatientId, setActivePatientId] = useState<string | null>(null);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const internalSearchRef = useRef<HTMLInputElement>(null);
  const inputRef = searchInputRef ?? internalSearchRef;
  const activeOptionRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const hintId = useId();

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

  const activePatient =
    filteredPatients.find((patient) => patient.id === activePatientId) ?? filteredPatients[0];

  useLayoutEffect(() => {
    if (isSearchFocused) {
      activeOptionRef.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }, [activePatient?.id, searchQuery, isSearchFocused]);

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (
      event.nativeEvent.isComposing ||
      event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
      !['ArrowDown', 'ArrowUp', 'Enter'].includes(event.key)
    ) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    if (event.key === 'Enter') {
      if (activePatient && !event.repeat) {
        onSelectPatient(activePatient);
      }
      return;
    }

    if (filteredPatients.length === 0) return;

    const direction = event.key === 'ArrowDown' ? 1 : -1;
    setActivePatientId((current) => {
      const index = Math.max(0, filteredPatients.findIndex((patient) => patient.id === current));
      const nextIndex = Math.max(0, Math.min(index + direction, filteredPatients.length - 1));
      return filteredPatients[nextIndex].id;
    });
  };

  return (
    <aside
      className={`w-[320px] bg-[#F0F7FF] border-r border-[#BFDBFE] flex flex-col shrink-0 min-h-0 h-full transition-all duration-500 ${
        highlighted ? 'ring-2 ring-[#3B82F6] ring-inset bg-[#DBEAFE]/30' : ''
      }`}
    >
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
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Поиск пациента"
            aria-autocomplete="list"
            aria-expanded={true}
            aria-controls={listboxId}
            aria-describedby={hintId}
            aria-activedescendant={
              isSearchFocused && activePatient ? `${listboxId}-${activePatient.id}` : undefined
            }
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setActivePatientId(null);
            }}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setIsSearchFocused(false)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Поиск по ФИО, телефону или карте"
            className="w-[100%] pl-9 pr-3 py-2 bg-white text-xs text-[#0F172A] border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('');
                setActivePatientId(null);
                inputRef.current?.focus();
              }}
              aria-label="Очистить поиск пациента"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#0F172A]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <p id={hintId} className="mb-3 text-xs text-[#475569]">
          ↑↓ — перемещение · Enter — выбрать
        </p>

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
      <div
        id={listboxId}
        role="listbox"
        aria-label="Пациенты"
        className="flex-1 overflow-y-auto px-3 pt-3 pb-6 space-y-2.5"
      >
        {filteredPatients.length > 0 ? (
          filteredPatients.map((patient) => (
            <div
              key={patient.id}
              id={`${listboxId}-${patient.id}`}
              role="option"
              aria-label={patient.name}
              aria-selected={selectedPatient?.id === patient.id}
              ref={activePatient?.id === patient.id ? activeOptionRef : undefined}
              className={`rounded-xl transition-all ${
                isSearchFocused && activePatient?.id === patient.id
                  ? 'ring-2 ring-[#2563EB] ring-offset-2 ring-offset-[#F0F7FF]'
                  : ''
              }`}
            >
              <PatientCard
                patient={patient}
                isSelected={selectedPatient?.id === patient.id}
                onSelect={(p) => {
                  setActivePatientId(p.id);
                  onSelectPatient(selectedPatient?.id === p.id ? null : p);
                }}
              />
            </div>
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
