import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AnswerData, Patient } from '../types';
import { Sparkles, User, AlertTriangle } from 'lucide-react';
import { GapBanner } from './GapBanner';

interface AnswerBlockProps {
  answer: AnswerData;
  selectedPatient: Patient | null;
  onCitationClick: (sourceId: string) => void;
  conflictWarning?: string;
  onViewConflictSources?: () => void;
  hideQuestion?: boolean;
  considersHistory?: boolean;
  onCancelGap?: (gapId: string | number) => Promise<void>;
}

/**
 * Превращает метки [W1], [W2], [WEB1], [1], [2] в markdown-ссылки с якорем:
 *   [W1] → [W1](#citation-W1)
 * ReactMarkdown отрендерит их как <a href="#citation-W1">, а мы в компоненте `a`
 * перехватим href и вызовем onCitationClick.
 */
function linkifyCitations(text: string): string {
  return text.replace(
    /\[((?:Источник\s+)?[A-Za-z]*\d+)\]/g,
    (_match, id: string) => `[${id}](#citation-${id})`,
  );
}

function normalizeAnswerMarkdown(text: string): string {
  return text.replace(
    /^\s*[-*+]\s+(\*\*[^*]+\*\*:?)\s*$/gm,
    '$1',
  );
}

export const AnswerBlock: React.FC<AnswerBlockProps> = ({
  answer,
  selectedPatient,
  onCitationClick,
  conflictWarning,
  onViewConflictSources,
  hideQuestion = false,
  considersHistory = false,
  onCancelGap,
}) => {
  const getPersonalizationText = () => {
    if (!selectedPatient) return 'Без персонализации';
    const initials = `${selectedPatient.name.split(' ')[0]} ${selectedPatient.name.split(' ')[1]?.[0] || ''}.${selectedPatient.name.split(' ')[2]?.[0] || ''}.`;
    return `Персонализировано: ${initials}, ${selectedPatient.age} ${selectedPatient.sex}`;
  };

  return (
    <div className="space-y-4 max-w-[800px]">
      {!hideQuestion && (
        <div className="flex flex-col items-end">
          <div className="bg-[#2563EB] text-white px-4 py-3 rounded-2xl rounded-tr-xs shadow-xs text-sm font-medium">
            {answer.question}
          </div>
          <div className="text-[11px] text-[#475569] mt-1.5 flex items-center gap-1.5 px-1">
            <User className="w-3 h-3 text-[#94A3B8]" />
            <span>Регистратор, {answer.timestamp}</span>
          </div>
        </div>
      )}

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

      {answer.wikiStrongMatch === false && !conflictWarning && (
        <div className="bg-[#FFFBEB] border-l-4 border-[#F59E0B] p-4 rounded-r-xl shadow-xs text-xs text-[#92400E] flex items-start gap-2.5">
          <AlertTriangle className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm text-[#B45309] mb-0.5">
              Ответ не из базы знаний
            </p>
            <p>
              В базе знаний MedTrust нет точного ответа на этот вопрос.
              Ответ основан на общих знаниях модели и не подтверждён источниками клиники.
              Рекомендуется уточнить у профильного специалиста.
            </p>
          </div>
        </div>
      )}

      {answer.gap?.created &&
        answer.gap.id !== undefined &&
        !answer.gap.cancelled &&
        onCancelGap && (
          <GapBanner
            gapId={answer.gap.id}
            source={answer.gap.source}
            onCancel={onCancelGap}
          />
        )
      }

      <div className="bg-white rounded-xl border border-[#BFDBFE] p-6 shadow-sm relative overflow-hidden">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-[#EFF6FF]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#DBEAFE] flex items-center justify-center text-[#2563EB]">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-semibold text-sm text-[#0F172A]">Ответ базы знаний</span>
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
              selectedPatient 
                ? 'bg-[#DBEAFE] text-[#1D4ED8] border border-[#93C5FD]' 
                : 'bg-slate-100 text-[#475569] border border-slate-200'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${selectedPatient ? 'bg-[#2563EB]' : 'bg-[#94A3B8]'}`} />
              {getPersonalizationText()}
            </span>
            {considersHistory && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-[#DBEAFE] text-[#2563EB]">
                Учитывает историю диалога
              </span>
            )}
          </div>
        </div>

        <div className="space-y-4 text-sm leading-relaxed text-[#0F172A] answer-markdown">
          {answer.sections.map((section, idx) => (
            <div key={idx}>
              {idx > 0 && section.title && (
                <h4 className="font-semibold text-[#0F172A] text-sm flex items-center gap-1.5 mt-2 mb-1">
                  <span className="w-1.5 h-4 bg-[#2563EB] rounded-full inline-block" />
                  <span>{section.title}</span>
                </h4>
              )}
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => (
                    <p className="mb-2 last:mb-0">{children}</p>
                  ),
                  h1: ({ children }) => (
                    <h5 className="font-semibold text-[#0F172A] text-sm mt-3 mb-1 first:mt-0">
                      {children}
                    </h5>
                  ),
                  h2: ({ children }) => (
                    <h5 className="font-semibold text-[#0F172A] text-sm mt-3 mb-1 first:mt-0">
                      {children}
                    </h5>
                  ),
                  h3: ({ children }) => (
                    <h5 className="font-semibold text-[#0F172A] text-sm mt-3 mb-1 first:mt-0">
                      {children}
                    </h5>
                  ),
                  h4: ({ children }) => (
                    <h5 className="font-semibold text-[#0F172A] text-sm mt-3 mb-1 first:mt-0">
                      {children}
                    </h5>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-[#0F172A]">{children}</strong>
                  ),
                  em: ({ children }) => <em className="italic">{children}</em>,
                  ul: ({ children }) => (
                    <ul className="list-disc list-outside ml-5 my-2 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-outside ml-5 my-2 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => <li className="pl-1">{children}</li>,
                  a: ({ href, children }) => {
                    // Перехватываем якоря вида #citation-W1
                    if (href && href.startsWith('#citation-')) {
                      const sourceId = href.slice('#citation-'.length);
                      return (
                        <button
                          type="button"
                          onClick={() => onCitationClick(sourceId)}
                          className="inline-flex items-center justify-center font-bold text-xs text-[#3B82F6] hover:text-[#1D4ED8] hover:underline px-1 py-0.5 rounded bg-[#EFF6FF] border border-[#BFDBFE] mx-0.5 transition-colors cursor-pointer"
                          title={`Перейти к источнику [${sourceId}]`}
                        >
                          [{sourceId}]
                        </button>
                      );
                    }
                    // Обычные ссылки — открываем в новой вкладке
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#2563EB] underline hover:text-[#1D4ED8]"
                      >
                        {children}
                      </a>
                    );
                  },
                  code: ({ children }) => (
                    <code className="bg-[#EFF6FF] px-1 py-0.5 rounded text-[12px] font-mono">
                      {children}
                    </code>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-[#3B82F6] pl-3 my-2 italic text-[#475569]">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="text-xs border-collapse w-full">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-[#DBEAFE] bg-[#EFF6FF] px-2 py-1 text-left font-semibold">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-[#DBEAFE] px-2 py-1">{children}</td>
                  ),
                  hr: () => <hr className="my-3 border-[#DBEAFE]" />,
                }}
              >
                {linkifyCitations(normalizeAnswerMarkdown(section.text))}
              </ReactMarkdown>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};