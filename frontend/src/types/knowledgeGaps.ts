/** Domain types for the admin "Knowledge Base Gap Map" screen (MVP). */

export type GapStatus = 'open' | 'in_review' | 'resolved' | 'dismissed';

export type GapSource = 'automatic' | 'user_feedback';

export type GapReason =
  | 'no_knowledge_base_answer'
  | 'knowledge_incomplete'
  | 'knowledge_outdated'
  | 'knowledge_conflict';

export type GapSort = 'newest' | 'oldest' | 'longest';

export type GapPeriod = 'today' | '7d' | '30d' | 'custom';

export type AdminRole = 'kb_owner' | 'developer';

export type DismissReason = 'duplicate' | 'out_of_scope' | 'not_a_gap';

export interface KnowledgeSourceRef {
  id: string;
  title: string;
}

export interface GapFeedback {
  id: string;
  rating: 'positive' | 'negative';
  comment: string;
  reasonCode?: GapReason;
}

/** A KB owner's comment from `knowledge_gap_comments`; append-only. */
export interface GapComment {
  id: string;
  author: string;
  body: string;
  createdAt: string;
}

/**
 * One `knowledge_gaps` event as it is shown to the KB owner.
 *
 * The first iteration stores one event per `query_id`: automatic and
 * user-confirmed events are not merged. Diagnostic fields are read-only;
 * only `status`, `comments`, `resolvedAt` and `resolvedBy` change.
 */
export interface KnowledgeGap {
  id: string | number;
  queryId: string;
  conversationId: string;
  sourceMessageId: string;
  source: GapSource;
  status: GapStatus;
  rawQuestion: string;
  resolvedQuery: string;
  reason: GapReason;
  answerabilityReason: string;
  confidence?: number;
  sourceIds: KnowledgeSourceRef[];
  feedback?: GapFeedback;
  comments: GapComment[];
  webSearchUsed: boolean;
  // Legacy cluster metadata; owner-managed membership comes from the groups API.
  /** Сколько других пробелов бэк предлагает смержить с этим */
  suggestedMergeCount?: number;
  /** Канонический вопрос группы, к которой относится пробел */
  canonicalQuestion?: string;
  /** id кластера, к которому относится пробел (legacy, автоматический) */
  clusterId?: string | null;
  /** id кластера, который бэк предлагает как «похожий» */
  suggestedClusterId?: string | null;
  /** Насколько этот пробел похож на канонический вопрос (0..1) */
  similarityScore?: number | null;
  /** Тип связи с кластером */
  clusterMatchType?: 'unassigned' | 'suggested' | 'review_candidate' | 'owner_confirmed' | string;
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string;
  resolvedBy?: string;
}

export interface GapFilters {
  search: string;
  statuses: GapStatus[];
  sources: GapSource[];
  reasons: GapReason[];
}

export type GapGroupStatus = 'candidate' | GapStatus;

export interface GapGroupMember {
  gapId: number;
  question: string;
  status: GapStatus;
  occurrenceCount: number;
  firstSeenAt: string;
  lastSeenAt: string;
  similarity: number;
  assignmentSource: string;
  removedAt: string | null;
  removedBy: string | null;
  removalReason: string | null;
}

export interface KnowledgeGapGroup {
  id: number;
  title: string;
  representativeQuery: string;
  status: GapGroupStatus;
  activeMemberCount: number;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  confirmedBy: string | null;
  confirmedAt: string | null;
  members: GapGroupMember[];
}

export interface GapGroupConfirmRequest {
  member_ids: number[];
  author: string;
}

export interface GapGroupDetachRequest {
  reason: string;
  author: string;
}

export interface GapGroupResolveRequest {
  member_ids: number[];
  note: string;
  author: string;
  idempotency_key: string;
}

export interface GapGroupResolveResult {
  status: 'completed';
  group_id: number;
  resolved_count: number;
  resolved_gap_ids: number[];
}
