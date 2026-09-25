import React from 'react';
import { Source } from '../types';
import { ExternalLink, BookOpen, Quote } from 'lucide-react';

interface SourceCardProps {
  sources: Source[];
  highlightedId: number | null;
}

export const SourceCard: React.FC<SourceCardProps> = ({ sources, highlightedId }) => {
  return (
    <div className="space-y-3 max-w-[800px] mt-6">
      <div className="flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-[#2563EB]" />
        <h3 className="font-semibold text-base text-[#0F172A]">Источники</h3>
        <span className="text-xs text-[#94A3B8] bg-[#DBEAFE] text-[#1D4ED8] px-2 py-0.5 rounded-full font-medium">
          {sources.length} статьи wiki.js
        </span>
      </div>

      <div className="grid gap-3">
        {sources.map((src) => {
          const isHighlighted = highlightedId === src.id;
          return (
            <div
              key={src.id}
              id={`source-${src.id}`}
              className={`p-4 bg-white rounded-xl border-l-4 border-l-[#2563EB] border border-[#BFDBFE] transition-all hover:shadow-md ${
                isHighlighted ? 'ring-2 ring-[#3B82F6] bg-[#EFF6FF] shadow-sm' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#2563EB] text-white font-bold text-xs">
                    {src.id}
                  </span>
                  <h4 className="font-semibold text-sm text-[#0F172A]">
                    {src.title}
                  </h4>
                </div>
                <span className="text-xs text-[#94A3B8] shrink-0 font-medium">
                  {src.wikiDate}
                </span>
              </div>

              {/* Quote block */}
              <div className="bg-[#EFF6FF] p-3 rounded-lg border border-[#DBEAFE] my-2.5 text-xs text-[#475569] flex gap-2 italic">
                <Quote className="w-4 h-4 text-[#3B82F6] shrink-0 mt-0.5 not-italic" />
                <p>«{src.quote}»</p>
              </div>

              {/* Link */}
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
            </div>
          );
        })}
      </div>
    </div>
  );
};
