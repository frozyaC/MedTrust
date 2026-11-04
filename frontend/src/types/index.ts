export interface Patient {
  id: string;
  name: string;
  age: number;
  sex: 'Ж' | 'М';
  allergies: string[];
  chronic: string[];
  contraindications: string[];
  lastVisit?: string;
}

export interface Source {
  id: string;
  sourceType: 'wiki' | 'web';
  usedInAnswer: boolean;
  title: string;
  wikiDate: string;
  path?: string;
  quote: string;
  url: string;
}

export interface AnswerSection {
  title: string;
  key: 'summary' | 'prep' | 'important' | 'contraindications';
  text: string;
  citations: string[];
}

export interface AnswerData {
  question: string;
  timestamp: string;
  queryId?: string;
  personalizedPatient?: string;
  sections: AnswerSection[];
  sources: Source[];
  conflictWarning?: string;
  wikiStrongMatch?: boolean;
  usedSourceIds?: string[];

  /** Автоматически зафиксированный пробел в БЗ (из POST /query) */
  gap?: {
    created: boolean;
    /** id записи в knowledge_gaps; бэк может вернуть int (BIGSERIAL) или string */
    id?: string | number;
    source?: 'automatic' | 'user_feedback';
    /** Локальный флаг: пользователь отменил пробел через PATCH (status=dismissed) */
    cancelled?: boolean;
  };

  /** Признак, что ответ получен из веб-поиска (не из БЗ) */
  webSearchUsed?: boolean;

  /** Фронтовый флаг: бэк не нашёл ответа в локальной Wiki (no-answer) */
  noAnswer?: boolean;
}

/** Оценка ответа регистратором */
export type FeedbackRating = 'useful' | 'useless';

/** Статус одного сообщения в ленте диалога */
export type ConversationStatus =
  | 'loading'
  | 'answer'
  | 'no_answer'
  | 'conflict'
  | 'error';

/** Один элемент ленты: вопрос + ответ + источники + оценка */
export interface ConversationItem {
  id: string;
  question: string;
  timestamp: string;
  status: ConversationStatus;
  answer?: AnswerData;
  sourcesExpanded: boolean;
  feedback: FeedbackRating | null;
  webSearchState?: 'idle' | 'loading' | 'success' | 'error';
  webAnswer?: WebSearchData;
  webError?: string;
  /** query_id из бэка; сохраняется даже при no_answer, чтобы можно было отправить feedback */
  queryId?: string;
}

/** Демо-состояния экрана (переключаются через StateSelector) */
export type ScreenState =
  | 'empty'
  | 'ready'
  | 'loading'
  | 'answer'
  | 'no_answer'
  | 'conflict'
  | 'error'
  | 'history';

/** Ответ POST /api/v1/feedback */
export interface FeedbackResponse {
  status: string;
  gap_recorded: boolean;
}

/** Один источник из POST /api/v1/web-search */
export interface WebSearchSource {
  source_id: string;
  title: string;
  url: string;
  domain: string;
  relevance: 'relevant' | 'low' | string;
  evidence_status: 'supported_candidate' | 'unverified' | string;
  content_type: 'page' | 'search_snippet' | string;
}

/** Ответ POST /api/v1/web-search (ручной веб-поиск) */
export interface WebSearchData {
  status: 'success' | 'disabled' | 'api_error' | 'no_results' | string;
  answer: string;
  sources: WebSearchSource[];
  warning?: string;
  diagnostics?: Record<string, unknown>;
}