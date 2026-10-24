import { AnswerData, ConversationItem, Patient, Source } from '../types';

export class QueryApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'QueryApiError';
  }
}

interface QueryPatientPayload {
  age?: number;
  sex?: string;
  contraindications: string[];
  anamnesis?: string;
}

interface QuerySource {
  source_id: string;
  source_type: 'wiki' | 'web';
  title: string;
  section: string | null;
  path: string | null;
  url: string | null;
  snippet: string | null;
  citation?: string;
  used_in_answer?: boolean;
}

interface SourceEvidenceCheck {
  wiki_strong_match?: boolean;
  web_search_status?: string;
}

interface AnswerReviewDiagnostics {
  source_evidence_check?: SourceEvidenceCheck;
  used_source_ids?: string[];
}

interface QueryResponse {
  query_id: string;
  conversation_id?: string;
  answer: string;
  sources: QuerySource[];
  answer_review_diagnostics?: AnswerReviewDiagnostics;
}

interface StoredChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  query_id: string | null;
  sources: unknown;
  created_at: string;
}

const NO_ANSWER_TEXT = 'не найден подтверждающий источник';
const TIME_FORMAT: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' };

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
}

function formatTimestamp(iso?: string): string {
  const date = iso ? new Date(iso) : new Date();
  if (Number.isNaN(date.getTime())) {
    return new Date().toLocaleTimeString('ru-RU', TIME_FORMAT);
  }
  return date.toLocaleTimeString('ru-RU', TIME_FORMAT);
}

function toQuerySources(sources: unknown): QuerySource[] {
  if (!Array.isArray(sources)) return [];
  return sources.map((raw, index) => {
    const source = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
    return {
      source_id:
        typeof source.source_id === 'string'
          ? source.source_id
          : typeof source.source_number === 'number'
            ? String(source.source_number)
            : String(index + 1),
      source_type: source.source_type === 'web' ? 'web' : 'wiki',
      title: typeof source.title === 'string' ? source.title : '',
      section: typeof source.section === 'string' ? source.section : null,
      path: typeof source.path === 'string' ? source.path : null,
      snippet: typeof source.snippet === 'string' ? source.snippet : null,
      url: typeof source.url === 'string' ? source.url : null,
      citation: typeof source.citation === 'string' ? source.citation : undefined,
      used_in_answer: typeof source.used_in_answer === 'boolean' ? source.used_in_answer : undefined,
    };
  });
}

export function toPatientPayload(patient: Patient | null): QueryPatientPayload | undefined {
  if (!patient) return undefined;

  const contraindications = [...patient.contraindications, ...patient.allergies].filter(Boolean);
  const anamnesis = patient.chronic.length > 0 ? patient.chronic.join(', ') : undefined;

  return {
    age: patient.age,
    sex: patient.sex,
    contraindications,
    ...(anamnesis ? { anamnesis } : {}),
  };
}

export function extractCitations(answer: string): { text: string; citations: string[] } {
  const pattern = /\[(?:Источник\s+)?([A-Za-z]*\d+)\]/g;
  const citations = [...new Set(
    [...answer.matchAll(pattern)].map((match) => match[1]),
  )];
  
  return { text: answer, citations };
}

export function mapQueryResponse(
  question: string,
  data: QueryResponse,
  timestamp?: string,
): AnswerData {
  const { text, citations } = extractCitations(data.answer);

  const sources: Source[] = data.sources
    .filter((source) => source.used_in_answer !== false)
    .map((source) => ({
      id: source.source_id,
      sourceType: source.source_type,
      usedInAnswer: source.used_in_answer ?? true,
      title: source.title,
      wikiDate: source.section ?? '',
      path: source.path ?? '',
      quote: source.snippet ?? '',
      url: source.url ?? '',
    }));

  const diagnostics = data.answer_review_diagnostics;
  const wikiStrongMatch = diagnostics?.source_evidence_check?.wiki_strong_match;
  const usedSourceIds = diagnostics?.used_source_ids;

  return {
    question,
    timestamp: timestamp ?? formatTimestamp(),
    queryId: data.query_id,
    sections: [
      {
        key: 'summary',
        title: 'Кратко',
        text,
        citations,
      },
    ],
    sources,
    wikiStrongMatch,
    usedSourceIds,
  };
}

export function isNoAnswer(data: QueryResponse): boolean {
  const answerText = (data.answer ?? '').trim();

  if (!answerText) return true;

  if (answerText.toLowerCase().includes(NO_ANSWER_TEXT)) return true;

  return false;
}

export async function askKnowledgeBase(
  question: string,
  patient: Patient | null,
  conversationId?: string,
): Promise<QueryResponse> {
  const patientPayload = toPatientPayload(patient);
  const response = await fetch(`${apiBaseUrl()}/api/v1/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      top_k: 5,
      ...(patientPayload ? { patient: patientPayload } : {}),
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
  });

  if (!response.ok) {
    let detail = `Ошибка запроса: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') {
        detail = payload.detail;
      }
    } catch {
      // keep status message
    }
    throw new QueryApiError(detail, response.status);
  }

  return response.json() as Promise<QueryResponse>;
}

export async function askAndBuildItem(
  question: string,
  patient: Patient | null,
  id: string,
  timestamp: string,
  conversationId?: string,
): Promise<{ item: ConversationItem; conversationId?: string }> {
  try {
    const data = await askKnowledgeBase(question, patient, conversationId);
    const answer = mapQueryResponse(question, data, timestamp);
    const noAnswer = isNoAnswer(data);

    return {
      item: {
        id,
        question,
        timestamp,
        status: noAnswer ? 'no_answer' : 'answer',
        answer: noAnswer ? undefined : answer,
        sourcesExpanded: false,
        feedback: null,
      },
      conversationId: data.conversation_id,
    };
  } catch {
    return {
      item: {
        id,
        question,
        timestamp,
        status: 'error',
        sourcesExpanded: false,
        feedback: null,
      },
    };
  }
}

function itemFromUserMessage(user: StoredChatMessage): ConversationItem {
  return {
    id: user.id,
    question: user.content,
    timestamp: formatTimestamp(user.created_at),
    status: 'error',
    sourcesExpanded: false,
    feedback: null,
  };
}

function itemFromPair(user: StoredChatMessage, assistant: StoredChatMessage): ConversationItem {
  const data: QueryResponse = {
    query_id: assistant.query_id ?? user.query_id ?? user.id,
    answer: assistant.content,
    sources: toQuerySources(assistant.sources),
  };
  const noAnswer = isNoAnswer(data);
  const timestamp = formatTimestamp(assistant.created_at || user.created_at);

  return {
    id: assistant.id,
    question: user.content,
    timestamp,
    status: noAnswer ? 'no_answer' : 'answer',
    answer: noAnswer ? undefined : mapQueryResponse(user.content, data, timestamp),
    sourcesExpanded: false,
    feedback: null,
  };
}

export function messagesToConversationItems(messages: StoredChatMessage[]): ConversationItem[] {
  const items: ConversationItem[] = [];
  let pendingUser: StoredChatMessage | null = null;

  for (const message of messages) {
    if (message.role === 'user') {
      if (pendingUser) items.push(itemFromUserMessage(pendingUser));
      pendingUser = message;
      continue;
    }
    if (message.role === 'assistant' && pendingUser) {
      items.push(itemFromPair(pendingUser, message));
      pendingUser = null;
    }
  }

  if (pendingUser) items.push(itemFromUserMessage(pendingUser));
  return items;
}

export async function loadConversationItems(conversationId: string): Promise<ConversationItem[]> {
  let response: Response;
  try {
    response = await fetch(
      `${apiBaseUrl()}/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
    );
  } catch {
    throw new QueryApiError('Не удалось загрузить историю диалога');
  }

  if (!response.ok) {
    let detail = `Ошибка загрузки истории: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') {
        detail = payload.detail;
      }
    } catch {
      // keep status message
    }
    throw new QueryApiError(detail, response.status);
  }

  const payload = (await response.json()) as { messages?: StoredChatMessage[] };
  return messagesToConversationItems(payload.messages ?? []);
}