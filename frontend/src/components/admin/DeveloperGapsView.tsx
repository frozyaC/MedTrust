import { useMemo, useState } from 'react';
import { ChevronDown, Code2, RotateCcw, Search, X } from 'lucide-react';
import { GapStatus, KnowledgeGap } from '../../types/knowledgeGaps';
import { STATUS_OPTIONS } from '../../data/knowledgeGaps';
import { matchesSearch } from '../../lib/format';
import { StatusBadge } from './GapBadges';

interface DeveloperGapsViewProps {
  gaps: KnowledgeGap[];
  periodLabel: string;
}

export function DeveloperGapsView({ gaps, periodLabel }: DeveloperGapsViewProps) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<GapStatus | 'all'>('all');

  const filtered = useMemo(
    () =>
      gaps.filter((gap) => {
        if (!matchesSearch(gap, search)) return false;
        if (status !== 'all' && gap.status !== status) return false;
        return true;
      }),
    [gaps, search, status],
  );

  const reset = () => {
    setSearch('');
    setStatus('all');
  };

  return (
    <section className="overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-card">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-med-border px-4 py-4">
        <div>
          <h2 className="text-xl font-semibold leading-7 text-med-text-primary">
            Технический список
          </h2>
          <p className="mt-0.5 text-xs leading-4 text-med-text-muted">
            query_id, тексты запросов, причина недостаточности и статус
          </p>
        </div>

        <span className="inline-flex items-center gap-1.5 rounded-full border border-med-border bg-med-primary-light/60 px-2.5 py-1 text-xs font-medium text-med-primary-hover">
          <Code2 className="h-3.5 w-3.5" />
          Без персональных данных
        </span>
      </header>

      <div className="flex flex-wrap items-center gap-2 border-b border-med-border bg-med-bg/30 px-4 py-3">
        <div className="relative min-w-[260px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-med-text-muted" />
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по тексту вопроса"
            aria-label="Поиск по тексту вопроса"
            className="h-9 w-full rounded-lg border border-med-border bg-med-surface pl-9 pr-9 text-sm text-med-text-primary outline-none transition-colors placeholder:text-med-text-muted focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-med-text-muted transition-colors hover:bg-med-bg hover:text-med-text-primary"
              aria-label="Очистить поиск"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="relative">
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as GapStatus | 'all')}
            aria-label="Статус"
            className="h-9 appearance-none rounded-lg border border-med-border bg-med-surface pl-3 pr-9 text-sm text-med-text-secondary outline-none transition-colors hover:border-med-border-strong focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
          >
            <option value="all">Все статусы</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-med-text-muted" />
        </div>

        <button
          type="button"
          onClick={reset}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-med-border bg-med-surface px-3 text-sm font-medium text-med-text-secondary transition-colors hover:border-med-border-strong hover:bg-med-bg hover:text-med-primary"
        >
          <RotateCcw className="h-4 w-4" />
          Сбросить
        </button>
      </div>

      {filtered.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] table-fixed border-collapse text-left">
            <colgroup>
              <col className="w-[286px]" />
              <col className="w-[210px]" />
              <col className="w-[180px]" />
              <col className="w-[224px]" />
              <col className="w-[100px]" />
            </colgroup>
            <thead className="bg-med-bg/50">
              <tr>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                  query_id
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                  Исходный вопрос
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                  Нормализованный запрос
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                  Причина недостаточности
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((gap, index) => (
                <tr
                  key={gap.id}
                  className={`border-t border-med-border/70 ${
                    index % 2 === 1 ? 'bg-med-bg/30' : 'bg-med-surface'
                  }`}
                >
                  <td className="px-3 py-3 align-top">
                    <span
                      className="break-all font-mono text-xs leading-4 text-med-text-secondary"
                      title={gap.queryId}
                    >
                      {gap.queryId}
                    </span>
                  </td>
                  <td className="px-3 py-3 align-top">
                    <span
                      className="line-clamp-2 text-sm leading-5 text-med-text-primary"
                      title={gap.rawQuestion}
                    >
                      {gap.rawQuestion}
                    </span>
                  </td>
                  <td className="px-3 py-3 align-top">
                    <span
                      className="line-clamp-2 text-sm leading-5 text-med-text-secondary"
                      title={gap.resolvedQuery}
                    >
                      {gap.resolvedQuery || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3 align-top">
                    <span
                      className="line-clamp-3 text-xs leading-4 text-med-text-secondary"
                      title={gap.answerabilityReason}
                    >
                      {gap.answerabilityReason}
                    </span>
                  </td>
                  <td className="px-3 py-3 align-top">
                    <StatusBadge status={gap.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-med-primary-light text-med-primary">
            <Search className="h-6 w-6" />
          </div>
          <h3 className="mt-3 text-base font-semibold text-med-text-primary">
            Нет пробелов по выбранным фильтрам
          </h3>
          <p className="mt-1 text-sm text-med-text-secondary">
            Измените поисковый запрос или сбросьте фильтр статуса.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg border border-med-border-strong bg-med-surface px-4 text-sm font-semibold text-med-primary transition-colors hover:bg-med-primary-light/40"
          >
            <RotateCcw className="h-4 w-4" />
            Сбросить
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-med-border px-4 py-2.5">
        <span className="text-xs text-med-text-muted">
          Показано {filtered.length} из {gaps.length} {periodLabel}
        </span>
        <span className="text-xs text-med-text-muted">
          Только идентификаторы и текст запросов · без ФИО и данных пациента
        </span>
      </div>
    </section>
  );
}
