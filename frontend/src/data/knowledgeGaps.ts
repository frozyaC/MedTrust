import {
  DismissReason,
  GapFilters,
  GapPeriod,
  GapReason,
  GapSort,
  GapSource,
  GapStatus,
  KnowledgeGap,
} from '../types/knowledgeGaps';

export const DEFAULT_STATUS_FILTER: GapStatus[] = ['open', 'in_review'];

export const STATUS_OPTIONS: Array<{ value: GapStatus; label: string; dotClass: string }> = [
  { value: 'open', label: 'Открыт', dotClass: 'bg-med-warning' },
  { value: 'in_review', label: 'В работе', dotClass: 'bg-med-primary' },
  { value: 'resolved', label: 'Закрыт', dotClass: 'bg-med-success' },
  { value: 'dismissed', label: 'Отклонён', dotClass: 'bg-med-text-muted' },
];

export const SOURCE_OPTIONS: Array<{ value: GapSource; label: string; dotClass: string }> = [
  { value: 'automatic', label: 'Авто', dotClass: 'bg-med-primary' },
  { value: 'user_feedback', label: 'Обратная связь', dotClass: 'bg-med-warning' },
];

export const REASON_OPTIONS: Array<{ value: GapReason; label: string; dotClass: string }> = [
  {
    value: 'no_knowledge_base_answer',
    label: 'Нет ответа в БЗ',
    dotClass: 'bg-med-primary',
  },
  {
    value: 'knowledge_incomplete',
    label: 'Ответ неполный',
    dotClass: 'bg-med-warning',
  },
  {
    value: 'knowledge_outdated',
    label: 'Информация устарела',
    dotClass: 'bg-med-warning',
  },
  {
    value: 'knowledge_conflict',
    label: 'Конфликт источников',
    dotClass: 'bg-med-error',
  },
];

export const DISMISS_REASON_OPTIONS: Array<{
  value: DismissReason;
  label: string;
  description: string;
}> = [
  {
    value: 'duplicate',
    label: 'Дубликат',
    description: 'Такой пробел уже есть в списке.',
  },
  {
    value: 'out_of_scope',
    label: 'Вне зоны ответственности',
    description: 'Вопрос не относится к базе знаний.',
  },
  {
    value: 'not_a_gap',
    label: 'Не является пробелом',
    description: 'Ответа в БЗ достаточно.',
  },
];

export const SORT_OPTIONS: Array<{ value: GapSort; label: string }> = [
  { value: 'newest', label: 'Сначала новые' },
  { value: 'oldest', label: 'Сначала старые' },
  { value: 'longest', label: 'Дольше всего в работе' },
];

export const PERIOD_OPTIONS: Array<{ value: GapPeriod; label: string }> = [
  { value: 'today', label: 'Сегодня' },
  { value: '7d', label: '7 дней' },
  { value: '30d', label: '30 дней' },
  { value: 'custom', label: 'Произвольный период' },
];

export const DEFAULT_FILTERS: GapFilters = {
  search: '',
  statuses: DEFAULT_STATUS_FILTER,
  sources: SOURCE_OPTIONS.map((option) => option.value),
  reasons: REASON_OPTIONS.map((option) => option.value),
};

export const DEMO_ADMIN_USER = {
  name: 'Смирнова Е.В.',
  role: 'Заведующий регистратурой',
  roleShort: 'Владелец БЗ',
  avatar: 'СЕ',
};

export const DEMO_DEVELOPER_USER = {
  name: 'Техническая команда',
  role: 'Разработчик',
  roleShort: 'Технический вид',
  avatar: 'ТК',
};
