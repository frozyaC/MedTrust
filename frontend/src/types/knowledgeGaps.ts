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

/**
 * One `knowledge_gaps` event as it is shown to the KB owner.
 *
 * The first iteration stores one event per `query_id`: automatic and
 * user-confirmed events are not merged. Diagnostic fields are read-only;
 * only `status`, `ownerComment`, `resolvedAt` and `resolvedBy` change.
 */
export interface KnowledgeGap {
  id: string;
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
  ownerComment: string;
  webSearchUsed: boolean;
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
