import {
  MAX_SUGGESTIONS,
  SuggestionQuestion,
  SuggestionQuestionsConfig,
} from '../types/suggestionQuestions';

const STORAGE_KEY = 'medtrust.suggestionQuestions';

export const DEFAULT_SUGGESTIONS: SuggestionQuestionsConfig = {
  version: 1,
  suggestions: [
    { id: 'sug-prep', label: 'Подготовка' },
    { id: 'sug-price', label: 'Стоимость' },
    { id: 'sug-repeat', label: 'Повторный прием' },
    { id: 'sug-first', label: 'Первичный прием' },
    { id: 'sug-doctor', label: 'Информация о враче' },
  ],
};

function isValidConfig(value: unknown): value is SuggestionQuestionsConfig {
  if (!value || typeof value !== 'object') return false;
  const config = value as Partial<SuggestionQuestionsConfig>;
  if (config.version !== 1) return false;
  if (!Array.isArray(config.suggestions)) return false;
  if (config.suggestions.length > MAX_SUGGESTIONS) return false;

  return config.suggestions.every(
    (s) =>
      s &&
      typeof s === 'object' &&
      typeof s.id === 'string' &&
      typeof s.label === 'string',
  );
}

export function loadSuggestions(): SuggestionQuestionsConfig {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_SUGGESTIONS);

    const parsed: unknown = JSON.parse(raw);
    if (!isValidConfig(parsed)) {
      return structuredClone(DEFAULT_SUGGESTIONS);
    }
    return parsed;
  } catch {
    return structuredClone(DEFAULT_SUGGESTIONS);
  }
}

export function saveSuggestions(config: SuggestionQuestionsConfig): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    
  }
}

export function resetSuggestions(): SuggestionQuestionsConfig {
  const fresh = structuredClone(DEFAULT_SUGGESTIONS);
  saveSuggestions(fresh);
  return fresh;
}

export function createSuggestionId(): string {
  return `sug-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function emptySuggestion(): SuggestionQuestion {
  return { id: createSuggestionId(), label: '' };
}