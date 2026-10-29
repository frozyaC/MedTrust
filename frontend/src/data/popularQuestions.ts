import {
  PopularQuestionCategory,
  PopularQuestionsConfig,
} from '../types/popularQuestions';

const STORAGE_KEY = 'medtrust.popularQuestions';

/**
 * Используется при первом запуске и при сбросе к заводским настройкам.
 */
export const DEFAULT_POPULAR_QUESTIONS: PopularQuestionsConfig = {
  version: 1,
  categories: [
    {
      id: 'cat-prep',
      name: 'Подготовка',
      presets: [
        { id: 'p-prep-1', label: 'Подготовка к анализу...', value: 'Подготовка к анализу ' },
        { id: 'p-prep-2', label: 'Подготовка к исследованию...', value: 'Подготовка к исследованию ' },
        { id: 'p-prep-3', label: 'Подготовка к процедуре...', value: 'Подготовка к процедуре ' },
        { id: 'p-prep-4', label: 'Противопоказания для...', value: 'Противопоказания для ' },
        { id: 'p-prep-5', label: 'Показания для...', value: 'Показания для ' },
      ],
    },
    {
      id: 'cat-appointment',
      name: 'Приём',
      presets: [
        { id: 'p-app-1', label: 'Первичный прием...', value: 'Первичный прием ' },
        { id: 'p-app-2', label: 'Повторный прием...', value: 'Повторный прием ' },
        { id: 'p-app-3', label: 'К кому записать...', value: 'К кому записать ' },
        { id: 'p-app-4', label: 'Информация о враче...', value: 'Информация о враче: ' },
      ],
    },
    {
      id: 'cat-services',
      name: 'Услуги и результаты',
      presets: [
        { id: 'p-serv-1', label: 'Состав анализа...', value: 'Состав анализа ' },
        { id: 'p-serv-2', label: 'Стоимость процедуры...', value: 'Стоимость процедуры ' },
        { id: 'p-serv-3', label: 'Получение результатов...', value: 'Получение результатов ' },
      ],
    },
  ],
};

/**
 * Валидация конфигурации — защита от битого localStorage.
 * Если структура не совпадает — возвращаем дефолт.
 */
function isValidConfig(value: unknown): value is PopularQuestionsConfig {
  if (!value || typeof value !== 'object') return false;
  const config = value as Partial<PopularQuestionsConfig>;
  if (config.version !== 1) return false;
  if (!Array.isArray(config.categories)) return false;

  return config.categories.every((cat) => {
    if (!cat || typeof cat !== 'object') return false;
    if (typeof cat.id !== 'string') return false;
    if (typeof cat.name !== 'string') return false;
    if (!Array.isArray(cat.presets)) return false;
    return cat.presets.every(
      (p) =>
        p &&
        typeof p === 'object' &&
        typeof p.id === 'string' &&
        typeof p.label === 'string' &&
        typeof p.value === 'string',
    );
  });
}

/**
 * Загрузка конфигурации из localStorage.
 * Если ничего нет или данные битые — возвращает дефолт.
 */
export function loadPopularQuestions(): PopularQuestionsConfig {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_POPULAR_QUESTIONS);

    const parsed: unknown = JSON.parse(raw);
    if (!isValidConfig(parsed)) {
      return structuredClone(DEFAULT_POPULAR_QUESTIONS);
    }
    return parsed;
  } catch {
    return structuredClone(DEFAULT_POPULAR_QUESTIONS);
  }
}

/**
 * Сохранение конфигурации в localStorage.
 */
export function savePopularQuestions(config: PopularQuestionsConfig): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    // quota / private mode — игнорируем, состояние остаётся в памяти
  }
}

/**
 * Сброс к заводским настройкам.
 */
export function resetPopularQuestions(): PopularQuestionsConfig {
  const fresh = structuredClone(DEFAULT_POPULAR_QUESTIONS);
  savePopularQuestions(fresh);
  return fresh;
}

/**
 * Хелпер: найти категорию по id.
 */
export function findCategory(
  config: PopularQuestionsConfig,
  categoryId: string,
): PopularQuestionCategory | undefined {
  return config.categories.find((c) => c.id === categoryId);
}