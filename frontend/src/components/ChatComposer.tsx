import React, { useEffect, useState } from 'react';
import { Search, Sparkles } from 'lucide-react';

interface ChatComposerProps {
  isLoading: boolean;
  suggestion: string;
  onSend: (query: string) => void;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({ isLoading, suggestion, onSend }) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (suggestion) setQuery(suggestion);
  }, [suggestion]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim() || isLoading) return;
    onSend(query.trim());
    setQuery('');
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white border-t border-[#BFDBFE] px-6 py-4 space-y-2 shrink-0">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Задайте уточняющий вопрос..."
            className="w-full pl-4 pr-10 py-3 text-sm text-[#0F172A] bg-white border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
          />
          <Sparkles className="w-4 h-4 text-[#3B82F6] absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none opacity-60" />
        </div>
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="px-6 py-3 bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-medium text-sm rounded-lg transition-colors shadow-xs flex items-center gap-2 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Search className="w-4 h-4" />
          <span>Спросить</span>
        </button>
      </div>
      <p className="text-xs text-[#475569] flex items-center gap-1.5 pl-1">
        <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
        Вопрос будет учтён вместе с предыдущими сообщениями диалога.
      </p>
    </form>
  );
};
