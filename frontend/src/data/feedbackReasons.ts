/**
 * Причины отрицательной оценки ответа.
 * Источник: Wiki/Feature-Karta-probelov-v-baze-znanij.md, раздел 5.
 *
 * ВАЖНО: коды должны совпадать с бэкендом.
 * Сейчас в Swagger POST /api/v1/feedback принимает только
 * { query_id, rating, comment }, без reason_code.
 * Пока отправляем код в начале comment, позже — отдельным полем.
 */

export type FeedbackReasonCode =
  | 'no_knowledge_base_answer'
  | 'knowledge_incomplete'
  | 'knowledge_outdated'
  | 'answer_irrelevant'
  | 'answer_incorrect'
  | 'answer_formatting'
  | 'wrong_context'
  | 'wrong_source'
  | 'technical_error'
  | 'other';

export type FeedbackRoute =
  | 'kb_owner'
  | 'developers'
  | 'developers_and_kb_owner'
  | 'by_comment';

export interface FeedbackReason {
  code: FeedbackReasonCode;
  /** Текст кнопки — точно как в документации */
  label: string;
  /** Короткое описание для подсказки */
  description?: string;
  /** Куда маршрутизируется проблема */
  routesTo: FeedbackRoute;
  /** Создаёт ли автоматически пробел в БЗ */
  createsGap: boolean;
  /** Обязателен ли комментарий */
  requiresComment: boolean;
  /** Рекомендуется ли комментарий (но не обязателен) */
  recommendsComment: boolean;
  /** Нужно ли подтверждение регистратора (для knowledge_incomplete) */
  requiresConfirmation: boolean;
}

export const FEEDBACK_REASONS: FeedbackReason[] = [
  {
    code: 'no_knowledge_base_answer',
    label: 'Нет ответа в базе знаний',
    description: 'Вопрос не покрыт корпоративной БЗ',
    routesTo: 'kb_owner',
    createsGap: true,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'knowledge_incomplete',
    label: 'Ответ неполный',
    description: 'Есть часть информации, но не всё',
    routesTo: 'kb_owner',
    createsGap: true,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: true,
  },
  {
    code: 'knowledge_outdated',
    label: 'Информация устарела',
    description: 'Источник содержит устаревшие данные',
    routesTo: 'kb_owner',
    createsGap: true,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'answer_irrelevant',
    label: 'Ответ не по моему вопросу',
    description: 'Найдено что-то близкое, но не то',
    routesTo: 'developers',
    createsGap: false,
    requiresComment: false,
    recommendsComment: true,
    requiresConfirmation: false,
  },
  {
    code: 'answer_incorrect',
    label: 'Ответ противоречит правилам или источнику',
    description: 'Содержание ответа неверно',
    routesTo: 'developers_and_kb_owner',
    createsGap: false,
    requiresComment: true,
    recommendsComment: true,
    requiresConfirmation: false,
  },
  {
    code: 'answer_formatting',
    label: 'Плохое форматирование или трудно читать',
    description: 'Неудобно использовать',
    routesTo: 'developers',
    createsGap: false,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'wrong_context',
    label: 'Не учтён контекст предыдущего вопроса',
    description: 'Ответ не учитывает историю диалога',
    routesTo: 'developers',
    createsGap: false,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'wrong_source',
    label: 'Показан неподходящий источник',
    description: 'Ссылка не относится к вопросу',
    routesTo: 'developers',
    createsGap: false,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'technical_error',
    label: 'Ошибка или ответ не загрузился',
    routesTo: 'developers',
    createsGap: false,
    requiresComment: false,
    recommendsComment: false,
    requiresConfirmation: false,
  },
  {
    code: 'other',
    label: 'Другая причина',
    description: 'Опишите в комментарии',
    routesTo: 'by_comment',
    createsGap: false,
    requiresComment: true,
    recommendsComment: true,
    requiresConfirmation: false,
  },
];

/**
 * Причины, которые точно создают пробел в БЗ.
 * Используется для UI: показать бейдж «Создаст пробел в БЗ».
 */
export const GAP_CREATING_REASONS: FeedbackReasonCode[] = FEEDBACK_REASONS
  .filter((r) => r.createsGap)
  .map((r) => r.code);

export function getFeedbackReason(code: FeedbackReasonCode): FeedbackReason | undefined {
  return FEEDBACK_REASONS.find((r) => r.code === code);
}