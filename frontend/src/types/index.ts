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