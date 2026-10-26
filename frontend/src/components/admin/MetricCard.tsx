interface MetricCardProps {
  label: string;
  value: string | number;
  hint: string;
  loading?: boolean;
}

export function MetricCard({ label, value, hint, loading = false }: MetricCardProps) {
  return (
    <article className="flex flex-col gap-1 rounded-xl border border-med-border bg-med-surface p-4 shadow-med-card">
      <div className="text-xs font-medium leading-4 text-med-text-muted">{label}</div>

      {loading ? (
        <div className="my-1 h-8 w-16 animate-pulse rounded-md bg-med-bg" aria-hidden="true" />
      ) : (
        <div className="text-2xl font-semibold leading-8 tracking-tight text-med-text-primary">
          {value}
        </div>
      )}

      <div className="text-xs leading-4 text-med-text-secondary">{hint}</div>
    </article>
  );
}
