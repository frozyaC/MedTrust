export interface SuggestionQuestion {
  id: string;
  label: string;
}

export interface SuggestionQuestionsConfig {
  version: 1;
  suggestions: SuggestionQuestion[];
}

export const MAX_SUGGESTIONS = 7;