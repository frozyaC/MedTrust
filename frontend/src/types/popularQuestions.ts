/**
 * Типы для «Популярных вопросов» — редактируемого списка заготовок,
 * который каждый регистратор настраивает под себя.
 *
 * В MVP хранится в localStorage. Когда появится API — структура
 * останется той же, добавится только загрузка/сохранение через fetch.
 */

export interface PopularQuestionPreset {
  id: string;
  /** Текст, который подставляется в поле ввода (обычно с пробелом в конце) */
  value: string;
  /** Текст на кнопке (обычно с «...» в конце) */
  label: string;
}

export interface PopularQuestionCategory {
  id: string;
  /** Название категории, например «Подготовка» */
  name: string;
  /** Пресеты внутри категории */
  presets: PopularQuestionPreset[];
}

export interface PopularQuestionsConfig {
  version: 1;
  categories: PopularQuestionCategory[];
}