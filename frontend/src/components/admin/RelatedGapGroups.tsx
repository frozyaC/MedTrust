import { useEffect, useState } from 'react';
import { fetchGapGroups, gapGroupErrorMessage } from '../../api/knowledgeGaps';
import type { KnowledgeGapGroup } from '../../types/knowledgeGaps';
import { GROUP_STATUS_LABELS } from './GapGroupPanel';

export function RelatedGapGroups({ gapId, onOpen }: { gapId: number; onOpen: (id: number) => void }) {
  const [groups, setGroups] = useState<KnowledgeGapGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchGapGroups({ gap_id: gapId }).then((loaded) => { if (active) setGroups(loaded); })
      .catch((err) => { if (active) setError(gapGroupErrorMessage(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [gapId, revision]);

  return <section className="space-y-2">
    <h3 className="text-xs font-semibold uppercase tracking-wider text-med-text-muted">Группы пробела</h3>
    {loading ? <p className="text-sm" role="status">Загрузка связанных групп…</p>
      : error ? <div role="alert" className="space-y-2 text-sm"><p>{error}</p><button className="text-med-primary underline" onClick={() => setRevision((value) => value + 1)}>Повторить</button></div>
      : groups.length ? groups.map((group) => <button key={group.id} className="block w-full rounded-lg border border-med-border p-3 text-left hover:bg-med-bg" onClick={() => onOpen(group.id)}>
        <span className="block text-sm font-medium text-med-primary">{group.title}</span>
        <span className="text-xs text-med-text-secondary">{GROUP_STATUS_LABELS[group.status]} · Участников: {group.activeMemberCount}</span>
      </button>) : <p className="text-sm text-med-text-secondary">Пробел пока не входит в группу.</p>}
  </section>;
}
