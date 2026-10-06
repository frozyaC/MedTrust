import React from 'react';
import { Patient } from '../types';
import { AlertCircle, Plus, RefreshCw, UserCheck } from 'lucide-react';

interface ConversationHeaderProps {
  patient: Patient | null;
  messageCount: number;
  onChangePatient: () => void;
  onNewConversation: () => void;
}

const patientSummary = (patient: Patient) => {
  const parts = patient.name.split(' ');
  const initials = `${parts[0]} ${parts[1]?.[0] || ''}.${parts[2]?.[0] || ''}.`;
  const allergies = patient.allergies.length ? `, аллергия на ${patient.allergies.join(', ')}` : '';
  const contraindications = patient.contraindications.length
    ? `, ${patient.contraindications.join(', ')}`
    : '';
  return `Пациент: ${initials}, ${patient.age} ${patient.sex}${allergies}${contraindications}`;
};

export const ConversationHeader: React.FC<ConversationHeaderProps> = ({
  patient,
  messageCount,
  onChangePatient,
  onNewConversation,
}) => (
  <div className="min-h-16 bg-white border-b border-[#BFDBFE] px-6 py-3 flex items-center gap-3 shrink-0">
    <div className="flex items-center gap-2 text-xs bg-[#EFF6FF] px-3.5 py-2.5 rounded-lg border border-[#DBEAFE] min-w-0">
      {patient ? (
        <>
          <UserCheck className="w-4 h-4 text-[#2563EB] shrink-0" />
          <span className="font-semibold text-[#2563EB] truncate">{patientSummary(patient)}</span>
        </>
      ) : (
        <>
          <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0" />
          <span className="text-[#475569]">Пациент не выбран — ответ без персонализации</span>
        </>
      )}
    </div>
    <button
      type="button"
      onClick={onChangePatient}
      className="px-3 py-2 text-xs font-semibold text-[#2563EB] bg-white border border-[#BFDBFE] rounded-lg hover:bg-[#EFF6FF] transition-colors inline-flex items-center gap-1.5 shrink-0"
    >
      <RefreshCw className="w-3.5 h-3.5" />
      Сменить
    </button>
    <button
      type="button"
      onClick={onNewConversation}
      className="px-3 py-2 text-xs font-semibold text-[#2563EB] bg-white border border-[#BFDBFE] rounded-lg hover:bg-[#EFF6FF] transition-colors inline-flex items-center gap-1.5 shrink-0"
    >
      <Plus className="w-3.5 h-3.5" />
      Новый диалог
    </button>
    <span className="ml-auto text-xs text-[#475569] whitespace-nowrap">Сообщений: {messageCount}</span>
  </div>
);
