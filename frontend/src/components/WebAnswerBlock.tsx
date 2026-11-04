import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Globe } from 'lucide-react';
import { WebSearchData } from '../types';

interface WebAnswerBlockProps {
  data: WebSearchData;
}

/**
 * Блок «Ответ из интернета» — рендерит answer из POST /api/v1/web-search.
 *
 * По договорённости answer показываем как есть (он уже содержит раздел
 * «Источники:» и предупреждение в конце), sources и warning отдельно не
 * дублируем. Стиль — жёлтая рамка + заголовок, чтобы визуально отличалось
 * от ответа базы знаний.
 */
export const WebAnswerBlock: React.FC<WebAnswerBlockProps> = ({ data }) => {
  const hasAnswer = Boolean(data.answer && data.answer.trim());
  return (
    <div className="max-w-[800px] rounded-xl border border-[#FDE68A] bg-[#FFFBEB] p-4 shadow-xs">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#FEF3C7] text-[#B45309]">
          <Globe className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold text-[#B45309]">Ответ из интернета</span>
        <span className="ml-auto rounded-full border border-[#FDE68A] bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#B45309]">
          Не проверено клиникой
        </span>
      </div>

      {hasAnswer ? (
        <div className="text-sm leading-relaxed text-[#0F172A] answer-markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              h1: ({ children }) => (
                <h5 className="mt-3 mb-1 text-sm font-semibold text-[#0F172A] first:mt-0">
                  {children}
                </h5>
              ),
              h2: ({ children }) => (
                <h5 className="mt-3 mb-1 text-sm font-semibold text-[#0F172A] first:mt-0">
                  {children}
                </h5>
              ),
              h3: ({ children }) => (
                <h5 className="mt-3 mb-1 text-sm font-semibold text-[#0F172A] first:mt-0">
                  {children}
                </h5>
              ),
              h4: ({ children }) => (
                <h5 className="mt-3 mb-1 text-sm font-semibold text-[#0F172A] first:mt-0">
                  {children}
                </h5>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-[#0F172A]">{children}</strong>
              ),
              em: ({ children }) => <em className="italic">{children}</em>,
              ul: ({ children }) => (
                <ul className="ml-5 my-2 list-disc space-y-1 list-outside">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="ml-5 my-2 list-decimal space-y-1 list-outside">{children}</ol>
              ),
              li: ({ children }) => <li className="pl-1">{children}</li>,
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#2563EB] underline hover:text-[#1D4ED8]"
                >
                  {children}
                </a>
              ),
              code: ({ children }) => (
                <code className="rounded bg-white px-1 py-0.5 font-mono text-[12px]">
                  {children}
                </code>
              ),
              blockquote: ({ children }) => (
                <blockquote className="my-2 border-l-2 border-[#F59E0B] pl-3 italic text-[#475569]">
                  {children}
                </blockquote>
              ),
              table: ({ children }) => (
                <div className="my-2 overflow-x-auto">
                  <table className="w-full border-collapse text-xs">{children}</table>
                </div>
              ),
              th: ({ children }) => (
                <th className="border border-[#FDE68A] bg-white px-2 py-1 text-left font-semibold">
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td className="border border-[#FDE68A] px-2 py-1">{children}</td>
              ),
              hr: () => <hr className="my-3 border-[#FDE68A]" />,
            }}
          >
            {data.answer}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="text-sm text-[#92400E]">
          Сервис веб-поиска не вернул текст ответа.
        </p>
      )}
    </div>
  );
};