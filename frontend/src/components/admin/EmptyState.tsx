import { Inbox, RotateCcw } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  resetLabel?: string;
  onReset: () => void;
}

export function EmptyState({
  title = 'Пробелов за выбранный период нет',
  description = 'Измените период или сбросьте фильтры, чтобы увидеть другие записи.',
  resetLabel = 'Сбросить фильтры',
  onReset,
}: EmptyStateProps) {
  return (
    <section className="flex flex-col items-center justify-center rounded-xl border border-med-border bg-med-surface px-6 py-14 text-center shadow-med-card">
      <div className="relative mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-med-primary-light text-med-primary">
        <Inbox className="h-8 w-8" />
        <span className="absolute -right-1 -top-1 h-3.5 w-3.5 rounded-full border-2 border-med-surface bg-med-warning" />
      </div>

      <h2 className="text-xl font-semibold leading-7 text-med-text-primary">{title}</h2>
      <p className="mt-1 max-w-[440px] text-sm leading-5 text-med-text-secondary">{description}</p>

      <button
        type="button"
        onClick={onReset}
        className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg border border-med-border-strong bg-med-surface px-4 text-sm font-semibold text-med-primary transition-colors hover:bg-med-primary-light/40"
      >
        <RotateCcw className="h-4 w-4" />
        {resetLabel}
      </button>
    </section>
  );
}
