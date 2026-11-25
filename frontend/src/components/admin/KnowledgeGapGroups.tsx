import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { fetchGapGroups, gapGroupErrorMessage } from '../../api/knowledgeGaps';
import type { GapGroupStatus, KnowledgeGapGroup } from '../../types/knowledgeGaps';
import { formatDateTime } from '../../lib/format';
import { GapGroupPanel, GROUP_STATUS_LABELS } from './GapGroupPanel';

interface Props {
  groupId: number | null;
  author: string;
  onSelectGroup: (groupId: number | null) => void;
  onOpenGap: (gapId: number) => void;
  onChanged: () => Promise<void>;
}

export function KnowledgeGapGroups({ groupId, author, onSelectGroup, onOpenGap, onChanged }: Props) {
  const [status, setStatus] = useState<GapGroupStatus | ''>('candidate');
  const [groups, setGroups] = useState<KnowledgeGapGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchGapGroups({ status: status || undefined }).then((loaded) => {
      if (active) setGroups(loaded);
    }).catch((err) => { if (active) setError(gapGroupErrorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [status, revision]);

  const changed = async () => {
    setRevision((value) => value + 1);
    await onChanged();
  };

  return <>
    <section className="overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-card" aria-busy={loading}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-med-border p-4">
        <label className="flex items-center gap-2 text-sm">Статус группы
          <select className="rounded-lg border border-med-border bg-med-surface p-2" value={status} onChange={(event) => setStatus(event.target.value as GapGroupStatus | '')}>
            <option value="">Все статусы</option>
            {Object.entries(GROUP_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg border border-med-border px-3 py-2 text-sm disabled:opacity-50" disabled={loading} onClick={() => setRevision((value) => value + 1)}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Обновить группы
        </button>
      </div>
      {loading ? <p className="p-6 text-sm" role="status">Загрузка групп…</p>
        : error ? <div className="space-y-3 p-6" role="alert"><p>{error}</p><button className="text-med-primary underline" onClick={() => setRevision((value) => value + 1)}>Повторить загрузку</button></div>
        : groups.length === 0 ? <div className="space-y-2 p-8 text-center"><p className="font-medium">Групп с выбранным статусом нет</p><p className="text-sm text-med-text-secondary">Предложения появляются, когда сервер находит похожие по смыслу пробелы.</p></div>
        : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead className="bg-med-bg text-xs text-med-text-secondary"><tr><th scope="col" className="p-4">Группа</th><th scope="col" className="p-4">Статус</th><th scope="col" className="p-4">Участников</th><th scope="col" className="p-4">Обновлена</th></tr></thead>
          <tbody>{groups.map((group) => <tr key={group.id} className="border-t border-med-border hover:bg-med-bg/50">
            <td className="p-4"><button className="text-left font-medium text-med-primary hover:underline" onClick={() => onSelectGroup(group.id)}>{group.title}</button></td>
            <td className="p-4">{GROUP_STATUS_LABELS[group.status]}</td><td className="p-4">{group.activeMemberCount}</td><td className="whitespace-nowrap p-4">{formatDateTime(group.updatedAt)}</td>
          </tr>)}</tbody>
        </table></div>}
    </section>
    {groupId !== null && <GapGroupPanel key={groupId} groupId={groupId} author={author} onClose={() => onSelectGroup(null)} onOpenGap={onOpenGap} onChanged={changed} />}
  </>;
}
