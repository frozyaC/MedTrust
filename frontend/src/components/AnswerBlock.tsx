import React from 'react';
import { AnswerData, Patient } from '../types';
import { Sparkles, User, AlertTriangle } from 'lucide-react';

interface AnswerBlockProps {
  answer: AnswerData;
  selectedPatient: Patient | null;
  onCitationClick: (citationId: number) => void;
  conflictWarning?: string;
  onViewConflictSources?: () => void;
}

export const AnswerBlock: React.FC<AnswerBlockProps> = ({
  answer,
  selectedPatient,
  onCitationClick,
  conflictWarning,
  onViewConflictSources,
}) => {
  const getPersonalizationText = () => {
    if (!selectedPatient) return 'Без персонализации';
    const initials = `${selectedPatient.name.split(' ')[0]} ${selectedPatient.name.split(' ')[1]?.[0] || ''}.${selectedPatient.name.split(' ')[2]?.[0] || ''}.`;
    return `Персонализировано: ${initials}, ${selectedPatient.age} ${selectedPatient.sex}`;
  };

  return (
    <div className="space-y-4 max-w-[800px]">
      {/* Question block (Right-aligned bubble) */}
      <div className="flex flex-col items-end">
        <div className="bg-[#2563EB] text-white px-4 py-3 rounded-2xl rounded-tr-xs shadow-xs text-sm font-medium">
          {answer.question}
        </div>
        <div className="text-[11px] text-[#475569] mt-1.5 flex items-center gap-1.5 px-1">
          <User className="w-3 h-3 text-[#94A3B8]" />
          <span>Регистратор, {answer.timestamp}</span>
        </div>
      </div>

      {/* Conflict Warning alert if active */}
      {conflictWarning && (
        <div className="bg-[#FFFBEB] border-l-4 border-[#F59E0B] p-4 rounded-r-xl shadow-xs text-xs text-[#92400E] flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm text-[#B45309] mb-0.5">Внимание</p>
              <p>{conflictWarning}</p>
            </div>
          </div>
          {onViewConflictSources && (
            <button
              onClick={onViewConflictSources}
              className="px-3 py-1.5 bg-[#F59E0B] text-white font-medium text-xs rounded-lg hover:bg-[#D97706] transition-colors shrink-0 shadow-xs"
            >
              Посмотреть источники
            </button>
          )}
        </div>
      )}

      {/* Answer Block (Left-aligned GPT-like card) */}
      <div className="bg-white rounded-xl border border-[#BFDBFE] p-6 shadow-sm relative overflow-hidden">
        {/* Top bar with Badge */}
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-[#EFF6FF]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#DBEAFE] flex items-center justify-center text-[#2563EB]">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-semibold text-sm text-[#0F172A]">Ответ базы знаний</span>
          </div>

          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
            selectedPatient 
              ? 'bg-[#DBEAFE] text-[#1D4ED8] border border-[#93C5FD]' 
              : 'bg-slate-100 text-[#475569] border border-slate-200'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${selectedPatient ? 'bg-[#2563EB]' : 'bg-[#94A3B8]'}`} />
            {getPersonalizationText()}
          </span>
        </div>

        {/* Answer Sections */}
        <div className="space-y-4 text-sm leading-relaxed text-[#0F172A]">
          {answer.sections.map((section, idx) => (
            <div key={idx} className="space-y-1">
              <h4 className="font-semibold text-[#0F172A] text-sm flex items-center gap-1.5">
                <span className="w-1.5 h-4 bg-[#2563EB] rounded-full inline-block" />
                <span>{section.title}</span>
              </h4>
              <p className="text-[#0F172A] pl-3">
                {section.text}{' '}
                {section.citations.map((c) => (
                  <button
                    key={c}
                    onClick={() => onCitationClick(c)}
                    className="inline-flex items-center justify-center font-bold text-xs text-[#3B82F6] hover:text-[#1D4ED8] hover:underline px-1 py-0.5 rounded bg-[#EFF6FF] border border-[#BFDBFE] mx-0.5 transition-colors cursor-pointer"
                    title={`Перейти к источнику [${c}]`}
                  >
                    [{c}]
                  </button>
                ))}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
