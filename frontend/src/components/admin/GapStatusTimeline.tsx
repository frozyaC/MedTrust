import { KnowledgeGap } from '../../types/knowledgeGaps';
import { formatDateTime } from '../../lib/format';

interface TimelineItem {
  key: string;
  label: string;
  date: string;
  dotClass: string;
  note?: string;
}

export function GapStatusTimeline({ gap }: { gap: KnowledgeGap }) {
  const items: TimelineItem[] = [
    {
      key: 'created',
      label: 'Создан',
      date: gap.createdAt,
      dotClass: 'bg-med-primary',
    },
    {
      key: 'updated',
      label: 'Обновлён',
      date: gap.updatedAt,
      dotClass: 'bg-med-text-muted',
    },
  ];

  if (gap.resolvedAt) {
    items.push({
      key: 'resolved',
      label: gap.status === 'dismissed' ? 'Отклонён' : 'Закрыт',
      date: gap.resolvedAt,
      dotClass: gap.status === 'dismissed' ? 'bg-med-text-muted' : 'bg-med-success',
      note: gap.resolvedBy ? `Ответственный: ${gap.resolvedBy}` : undefined,
    });
  }

  return (
    <ol className="relative space-y-3 before:absolute before:bottom-1 before:left-[3px] before:top-1 before:w-px before:bg-med-border">
      {items.map((item) => (
        <li key={item.key} className="relative pl-6">
          <span
            className={`absolute left-0 top-1.5 h-2 w-2 rounded-full ring-4 ring-med-surface ${item.dotClass}`}
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
            <span className="text-xs font-medium text-med-text-primary">{item.label}</span>
            <span className="text-xs text-med-text-muted">{formatDateTime(item.date)}</span>
          </div>
          {item.note && (
            <div className="mt-0.5 text-xs text-med-text-secondary">{item.note}</div>
          )}
        </li>
      ))}

      {!gap.resolvedAt && (
        <li className="relative pl-6">
          <span
            className="absolute left-0 top-1.5 h-2 w-2 rounded-full border border-med-border bg-med-surface ring-4 ring-med-surface"
            aria-hidden="true"
          />
          <div className="text-xs text-med-text-muted">Ещё не закрыт</div>
        </li>
      )}
    </ol>
  );
}
