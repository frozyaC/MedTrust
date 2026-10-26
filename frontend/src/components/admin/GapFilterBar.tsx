import { useEffect, useRef, useState } from 'react';
import { ArrowUpDown, ChevronDown, RotateCcw, Search, X } from 'lucide-react';
import {
  GapFilters,
  GapReason,
  GapSort,
  GapSource,
  GapStatus,
} from '../../types/knowledgeGaps';
import {
  REASON_OPTIONS,
  SORT_OPTIONS,
  SOURCE_OPTIONS,
  STATUS_OPTIONS,
} from '../../data/knowledgeGaps';

interface MultiSelectOption<T extends string> {
  value: T;
  label: string;
  dotClass?: string;
}

interface MultiSelectProps<T extends string> {
  label: string;
  options: MultiSelectOption<T>[];
  values: T[];
  onChange: (values: T[]) => void;
}

function MultiSelect<T extends string>({ label, options, values, onChange }: MultiSelectProps<T>) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const summary =
    values.length === options.length
      ? 'Все'
      : values.length === 0
        ? 'Ничего'
        : values.length === 1
          ? (options.find((option) => option.value === values[0])?.label ?? '1')
          : `${values.length} из ${options.length}`;

  const isNarrowed = values.length !== options.length;

  const toggle = (value: T) => {
    onChange(
      values.includes(value) ? values.filter((item) => item !== value) : [...values, value],
    );
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`${label}: ${summary}`}
        className={`inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm transition-colors ${
          isNarrowed
            ? 'border-med-border-strong bg-med-primary-light/50 text-med-primary-hover'
            : 'border-med-border bg-med-surface text-med-text-secondary hover:border-med-border-strong'
        }`}
      >
        <span className="font-medium">{label}</span>
        <span className={`text-xs ${isNarrowed ? 'text-med-primary' : 'text-med-text-muted'}`}>
          {summary}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-med-text-muted transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          className="absolute left-0 top-full z-30 mt-2 w-64 animate-fade-in rounded-xl border border-med-border bg-med-surface p-1.5 shadow-med-panel"
          role="group"
          aria-label={`Фильтр: ${label}`}
        >
          <div className="flex items-center justify-between px-2 py-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-med-text-muted">
              {label}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onChange(options.map((option) => option.value))}
                className="text-xs font-medium text-med-primary hover:underline"
              >
                Все
              </button>
              <button
                type="button"
                onClick={() => onChange([])}
                className="text-xs font-medium text-med-text-muted hover:text-med-text-secondary hover:underline"
              >
                Ничего
              </button>
            </div>
          </div>

          {options.map((option) => {
            const checked = values.includes(option.value);

            return (
              <label
                key={option.value}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-med-text-primary transition-colors hover:bg-med-bg"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(option.value)}
                  className="h-4 w-4 shrink-0 rounded border-med-border-strong accent-med-primary"
                />
                {option.dotClass && (
                  <span className={`h-2 w-2 shrink-0 rounded-full ${option.dotClass}`} />
                )}
                <span>{option.label}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface GapFilterBarProps {
  filters: GapFilters;
  onChange: (next: Partial<GapFilters>) => void;
  sort: GapSort;
  onSortChange: (sort: GapSort) => void;
  onReset: () => void;
}

export function GapFilterBar({
  filters,
  onChange,
  sort,
  onSortChange,
  onReset,
}: GapFilterBarProps) {
  return (
    <section
      className="rounded-xl border border-med-border bg-med-surface p-4 shadow-med-card"
      aria-label="Фильтры пробелов"
    >
      <div className="relative w-full">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-med-text-muted" />
        <input
          type="text"
          value={filters.search}
          onChange={(event) => onChange({ search: event.target.value })}
          placeholder="Поиск по вопросу или нормализованному запросу"
          aria-label="Поиск по вопросу или нормализованному запросу"
          className="h-10 w-full rounded-lg border border-med-border bg-med-surface pl-9 pr-9 text-sm text-med-text-primary outline-none transition-colors placeholder:text-med-text-muted focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onChange({ search: '' })}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-med-text-muted transition-colors hover:bg-med-bg hover:text-med-text-primary"
            aria-label="Очистить поиск"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2.5">
        <MultiSelect<GapStatus>
          label="Статус"
          options={STATUS_OPTIONS}
          values={filters.statuses}
          onChange={(statuses) => onChange({ statuses })}
        />

        <MultiSelect<GapSource>
          label="Источник"
          options={SOURCE_OPTIONS}
          values={filters.sources}
          onChange={(sources) => onChange({ sources })}
        />

        <MultiSelect<GapReason>
          label="Причина"
          options={REASON_OPTIONS}
          values={filters.reasons}
          onChange={(reasons) => onChange({ reasons })}
        />

        <div className="relative">
          <ArrowUpDown className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-med-text-muted" />
          <select
            value={sort}
            onChange={(event) => onSortChange(event.target.value as GapSort)}
            aria-label="Сортировка"
            className="h-10 appearance-none rounded-lg border border-med-border bg-med-surface pl-9 pr-9 text-sm text-med-text-secondary outline-none transition-colors hover:border-med-border-strong focus:border-med-primary focus:ring-2 focus:ring-med-primary/20"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-med-text-muted" />
        </div>

        <button
          type="button"
          onClick={onReset}
          className="ml-auto inline-flex h-10 items-center gap-2 rounded-lg border border-med-border bg-med-surface px-3 text-sm font-medium text-med-text-secondary transition-colors hover:border-med-border-strong hover:bg-med-bg hover:text-med-primary"
        >
          <RotateCcw className="h-4 w-4" />
          Сбросить фильтры
        </button>
      </div>
    </section>
  );
}
