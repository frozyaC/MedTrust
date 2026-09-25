import React from 'react';
import { ScreenState } from '../types';
import { Layers } from 'lucide-react';

interface StateSelectorProps {
  currentState: ScreenState;
  onSelectState: (state: ScreenState) => void;
}

export const StateSelector: React.FC<StateSelectorProps> = ({
  currentState,
  onSelectState,
}) => {
  const states: { id: ScreenState; label: string }[] = [
    { id: 'empty', label: '1. Пустое состояние' },
    { id: 'ready', label: '2. Пациент выбран' },
    { id: 'loading', label: '3. Загрузка' },
    { id: 'answer', label: '4. Ответ найден' },
    { id: 'no_answer', label: '5. Ответ не найден' },
    { id: 'conflict', label: '6. Конфликт источников' },
    { id: 'error', label: '7. Ошибка wiki.js' },
  ];

  return (
    <div className="bg-white border-b border-[#BFDBFE] px-6 py-2 flex items-center justify-between gap-4 text-xs">
      <div className="flex items-center gap-2 text-[#475569] font-medium shrink-0">
        <Layers className="w-4 h-4 text-[#2563EB]" />
        <span>Режим демонстрации:</span>
      </div>

      <div className="flex flex-wrap gap-1.5 overflow-x-auto py-1">
        {states.map((st) => {
          const isActive = currentState === st.id;
          return (
            <button
              key={st.id}
              onClick={() => onSelectState(st.id)}
              className={`px-2.5 py-1 rounded-md font-medium transition-all text-xs whitespace-nowrap ${
                isActive
                  ? 'bg-[#2563EB] text-white shadow-xs'
                  : 'bg-[#EFF6FF] text-[#475569] hover:bg-[#DBEAFE] hover:text-[#0F172A]'
              }`}
            >
              {st.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
