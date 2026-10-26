import { GapReason, GapSource, GapStatus } from '../../types/knowledgeGaps';
import { REASON_OPTIONS, SOURCE_OPTIONS, STATUS_OPTIONS } from '../../data/knowledgeGaps';

const STATUS_STYLES: Record<GapStatus, { container: string; dot: string }> = {
  open: {
    container: 'border-med-warning/40 bg-med-warning/10 text-med-text-primary',
    dot: 'bg-med-warning',
  },
  in_review: {
    container: 'border-med-border-strong bg-med-primary-light text-med-primary-hover',
    dot: 'bg-med-primary',
  },
  resolved: {
    container: 'border-med-success/30 bg-med-success/10 text-med-text-primary',
    dot: 'bg-med-success',
  },
  dismissed: {
    container: 'border-med-border bg-med-text-muted/10 text-med-text-secondary',
    dot: 'bg-med-text-muted',
  },
};

const SOURCE_STYLES: Record<GapSource, { container: string; dot: string }> = {
  automatic: {
    container: 'border-med-border-strong bg-med-primary-light text-med-primary-hover',
    dot: 'bg-med-primary',
  },
  user_feedback: {
    container: 'border-med-warning/40 bg-med-warning/10 text-med-text-primary',
    dot: 'bg-med-warning',
  },
};

const REASON_STYLES: Record<GapReason, { container: string; dot: string }> = {
  no_knowledge_base_answer: {
    container: 'border-med-border bg-med-primary-light/60 text-med-primary-hover',
    dot: 'bg-med-primary',
  },
  knowledge_incomplete: {
    container: 'border-med-warning/40 bg-med-warning/10 text-med-text-primary',
    dot: 'bg-med-warning',
  },
  knowledge_outdated: {
    container: 'border-med-warning/40 bg-med-warning/10 text-med-text-primary',
    dot: 'bg-med-warning',
  },
  knowledge_conflict: {
    container: 'border-med-error/30 bg-med-error/10 text-med-text-primary',
    dot: 'bg-med-error',
  },
};

function labelFor<T extends string>(
  options: Array<{ value: T; label: string }>,
  value: T,
  fallback: string,
): string {
  return options.find((option) => option.value === value)?.label ?? fallback;
}

export function StatusBadge({ status }: { status: GapStatus }) {
  const style = STATUS_STYLES[status];
  const label = labelFor(STATUS_OPTIONS, status, status);

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium ${style.container}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}

export function SourceBadge({ source }: { source: GapSource }) {
  const style = SOURCE_STYLES[source];
  const label = labelFor(SOURCE_OPTIONS, source, source);

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium ${style.container}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}

export function ReasonBadge({ reason }: { reason: GapReason }) {
  const style = REASON_STYLES[reason];
  const label = labelFor(REASON_OPTIONS, reason, reason);

  return (
    <span
      title={label}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-1 text-xs font-medium ${style.container}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}
