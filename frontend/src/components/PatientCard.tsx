import React from 'react';
import { Patient } from '../types';
import { User, Calendar, Check } from 'lucide-react';

interface PatientCardProps {
  patient: Patient;
  isSelected: boolean;
  onSelect: (patient: Patient) => void;
}

export const PatientCard: React.FC<PatientCardProps> = ({ patient, isSelected, onSelect }) => {
  return (
    <div
      onClick={() => onSelect(patient)}
      className={`p-3.5 rounded-[12px] cursor-pointer transition-all border ${
        isSelected
          ? 'bg-[#DBEAFE] border-[#2563EB] shadow-sm ring-1 ring-[#2563EB]'
          : 'bg-white border-[#BFDBFE] hover:border-[#93C5FD] hover:shadow-xs'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
            isSelected ? 'bg-[#2563EB] text-white' : 'bg-[#EFF6FF] text-[#2563EB]'
          }`}>
            <User className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-[#0F172A] leading-tight">
              {patient.name}
            </h3>
            <div className="text-xs text-[#475569] font-medium">
              {patient.age} {patient.age % 10 === 1 && patient.age !== 11 ? 'год' : (patient.age % 10 >= 2 && patient.age % 10 <= 4 && (patient.age < 10 || patient.age > 20)) ? 'года' : 'лет'}, {patient.sex}
            </div>
          </div>
        </div>
        {isSelected && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-[#2563EB] text-white font-medium flex items-center gap-1">
            <Check className="w-3 h-3" /> Выбран
          </span>
        )}
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 my-2">
        {patient.allergies.length > 0 ? (
          patient.allergies.map((allergy, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded-full text-xs font-medium bg-[#FEF2F2] text-[#EF4444] border border-[#FECACA]"
            >
              аллергия: {allergy}
            </span>
          ))
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-[#475569]">
            аллергия: нет
          </span>
        )}

        {patient.chronic.length > 0 ? (
          patient.chronic.map((chr, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-[#475569]"
            >
              хронические: {chr}
            </span>
          ))
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-[#475569]">
            хронические: нет
          </span>
        )}

        {patient.contraindications.length > 0 ? (
          patient.contraindications.map((contra, idx) => {
            const isPregnancy = contra.includes('беременность');
            return (
              <span
                key={idx}
                className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                  isPregnancy
                    ? 'bg-[#DBEAFE] text-[#1D4ED8] border-[#93C5FD]'
                    : 'bg-slate-100 text-[#475569] border-slate-200'
                }`}
              >
                {isPregnancy ? contra : `противопоказания: ${contra}`}
              </span>
            );
          })
        ) : (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-[#475569]">
            противопоказания: нет
          </span>
        )}
      </div>

      {patient.lastVisit && (
        <div className="text-[11px] text-[#94A3B8] flex items-center gap-1 mt-1">
          <Calendar className="w-3 h-3" />
          <span>Последний визит: {patient.lastVisit}</span>
        </div>
      )}
    </div>
  );
};
