import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Source } from '../types';
import { ExternalLink, BookOpen, Quote } from 'lucide-react';

interface SourceCardProps {
  sources: Source[];
  highlightedId: string | null;
  idPrefix?: string;
  showHeader?: boolean;
}

function cleanSection(section: string, title: string): string {
  if (!section) return '';

  let cleaned = section;

  // 1. Убираем markdown-заголовки в начале: "## ", "### ", "#### "
  cleaned = cleaned.replace(/^#{1,6}\s+/, '');

  // 2. Убираем markdown-ссылки: [текст](url) → текст
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  // 3. Убираем **жирный** и *курсив*
  cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
  cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');

  // 4. Если section начинается с title + " > " — обрезаем title
  const prefix = `${title} > `;
  if (cleaned.startsWith(prefix)) {
    cleaned = cleaned.slice(prefix.length);
  }
  if (cleaned === title) return '';

  // 5. Нормализуем разделители иерархии: " > " → " › "
  cleaned = cleaned.replace(/\s*>\s*/g, ' › ');

  // 6. Убираем trailing ":" и пробелы
  cleaned = cleaned.replace(/[:\s]+$/, '').trim();

  return cleaned;
}

export const SourceCard: React.FC<SourceCardProps> = ({
  sources,
  highlightedId,
  idPrefix = 'source',
  showHeader = true,
}) => {
  return (
    <div className={`space-y-3 max-w-[800px] ${showHeader ? 'mt-6' : 'mt-3'}`}>
      {showHeader && (
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-[#2563EB]" />
          <h3 className="font-semibold text-base text-[#0F172A]">Источники</h3>
          <span className="text-xs text-[#94A3B8] bg-[#DBEAFE] text-[#1D4ED8] px-2 py-0.5 rounded-full font-medium">
            {sources.length} статьи wiki.js
          </span>
        </div>
      )}

      <div className="grid gap-3">
        {sources.map((src) => {
          const isHighlighted = highlightedId === src.id;
          const section = cleanSection(src.wikiDate, src.title);
          return (
            <div
              key={src.id}
              id={`${idPrefix}-${src.id}`}
              className={`p-4 bg-white rounded-xl border-l-4 border-l-[#2563EB] border border-[#BFDBFE] transition-all hover:shadow-md ${
                isHighlighted ? 'ring-2 ring-[#3B82F6] bg-[#EFF6FF] shadow-sm' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-start gap-2 min-w-0">
                  <span className="inline-flex items-center justify-center min-w-6 h-6 px-1.5 rounded-md bg-[#2563EB] text-white font-bold text-xs shrink-0">
                    {src.id}
                  </span>
                  <div className="min-w-0">
                    <h4 className="font-semibold text-sm text-[#0F172A]">
                      {src.title}
                    </h4>
                    {src.path ? (
                      <p
                        className="text-[11px] text-[#94A3B8] font-normal truncate"
                        title={src.path}
                      >
                        {src.path}
                      </p>
                    ) : null}
                  </div>
                </div>
                {section ? (
                  <span className="text-xs text-[#475569] shrink-0 font-medium text-right bg-[#EFF6FF] px-2 py-0.5 rounded-md border border-[#DBEAFE]">
                    {section}
                  </span>
                ) : null}
              </div>

              <div className="bg-[#EFF6FF] p-3 rounded-lg border border-[#DBEAFE] my-2.5 text-xs text-[#475569] flex gap-2">
                <Quote className="w-4 h-4 text-[#3B82F6] shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1 prose-quote">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => (
                        <p className="italic mb-2 last:mb-0">{children}</p>
                      ),
                      h1: ({ children }) => (
                        <h5 className="italic font-semibold text-[#0F172A] text-xs mt-2 mb-1 first:mt-0">
                          {children}
                        </h5>
                      ),
                      h2: ({ children }) => (
                        <h5 className="italic font-semibold text-[#0F172A] text-xs mt-2 mb-1 first:mt-0">
                          {children}
                        </h5>
                      ),
                      h3: ({ children }) => (
                        <h5 className="italic font-semibold text-[#0F172A] text-xs mt-2 mb-1 first:mt-0">
                          {children}
                        </h5>
                      ),
                      h4: ({ children }) => (
                        <h5 className="italic font-semibold text-[#0F172A] text-xs mt-2 mb-1 first:mt-0">
                          {children}
                        </h5>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-[#0F172A]">{children}</strong>
                      ),
                      em: ({ children }) => <em className="italic">{children}</em>,
                      ul: ({ children }) => (
                        <ul className="list-disc list-inside my-1 space-y-0.5">{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="list-decimal list-inside my-1 space-y-0.5">{children}</ol>
                      ),
                      li: ({ children }) => <li className="italic">{children}</li>,
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
                        <code className="bg-white px-1 py-0.5 rounded text-[11px] font-mono">
                          {children}
                        </code>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-[#3B82F6] pl-2 my-1 italic">
                          {children}
                        </blockquote>
                      ),
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-2">
                          <table className="text-[11px] border-collapse w-full">
                            {children}
                          </table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th className="border border-[#DBEAFE] bg-white px-2 py-1 text-left font-semibold">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="border border-[#DBEAFE] px-2 py-1">{children}</td>
                      ),
                      hr: () => <hr className="my-2 border-[#DBEAFE]" />,
                    }}
                  >
                    {src.quote}
                  </ReactMarkdown>
                </div>
              </div>

              {src.url ? (
                <div className="flex justify-end pt-1">
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] hover:underline transition-colors"
                  >
                    <span>Открыть в wiki.js</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};