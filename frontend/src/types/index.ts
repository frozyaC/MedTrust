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
  personalizedPatient?: string;
  sections: AnswerSection[];
  sources: Source[];
  conflictWarning?: string;
}

export type ScreenState = 
  | 'empty' 
  | 'ready' 
  | 'loading' 
  | 'answer' 
  | 'no_answer' 
  | 'conflict' 
  | 'error';
