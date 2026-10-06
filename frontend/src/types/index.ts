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
  id: number;
  title: string;
  wikiDate: string;
  quote: string;
  url: string;
}

export interface AnswerSection {
  title: string;
  key: 'summary' | 'prep' | 'important' | 'contraindications';
  text: string;
  citations: number[];
}

export interface AnswerData {
  question: string;
  timestamp: string;
  queryId?: string;
  personalizedPatient?: string;
  sections: AnswerSection[];
  sources: Source[];
  conflictWarning?: string;
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