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

const HOUR = 60 * 60 * 1000;
const NOW = new Date();
const hoursAgo = (hours: number) => new Date(NOW.getTime() - hours * HOUR).toISOString();

/**
 * Demo data for the MVP mockup. The production screen should receive the same
 * shape from `GET /api/v1/knowledge-gaps` once the admin read endpoint exists.
 */
export const DEMO_GAPS: KnowledgeGap[] = [
  {
    id: 'f3a91c2e-7b44-4f0a-9c61-1d2e8b7a5c10',
    queryId: '8b1d6f3a-2c9e-4a71-b5d0-6e4f2a9c8b31',
    conversationId: 'c47e9a12-5b83-4d6f-a1c9-3f8e7d2b6041',
    sourceMessageId: 'd92b4c17-8e6a-4f3d-b7a1-5c0e9f2d8a63',
    source: 'automatic',
    status: 'open',
    rawQuestion: 'Сколько стоит гастроскопия с наркозом?',
    resolvedQuery: 'Стоимость гастроскопии с седацией (наркозом)',
    reason: 'no_knowledge_base_answer',
    answerabilityReason:
      'В БЗ есть стоимость гастроскопии без седации, но нет тарифа на проведение с анестезиологом.',
    confidence: 0.91,
    sourceIds: [
      {
        id: 'kb-gastro-219',
        title: 'Гастроскопия: подготовка и проведение',
      },
    ],
    ownerComment: '',
    webSearchUsed: true,
    createdAt: hoursAgo(2),
    updatedAt: hoursAgo(1.5),
  },
  {
    id: 'b7c240d8-1e93-4a6f-8d52-9f10c3e7a841',
    queryId: '3f6c9a21-7d84-4e02-b5c1-8a0d6f3e2b97',
    conversationId: '1a8f3d65-9c27-4b40-8e13-7d5c2a9f0b64',
    sourceMessageId: '6e2d9b48-1f70-4c35-a8d2-0b9e4f7c1a53',
    source: 'automatic',
    status: 'open',
    rawQuestion: 'Можно ли делать МРТ с кардиостимулятором?',
    resolvedQuery: 'МРТ при наличии кардиостимулятора: совместимость и ограничения',
    reason: 'knowledge_incomplete',
    answerabilityReason:
      'В статье перечислены общие противопоказания, но нет критериев совместимости кардиостимуляторов.',
    confidence: 0.86,
    sourceIds: [
      {
        id: 'kb-mri-104',
        title: 'МРТ: противопоказания и подготовка',
      },
      {
        id: 'kb-cardio-58',
        title: 'Кардиология: имплантируемые устройства',
      },
    ],
    ownerComment: '',
    webSearchUsed: false,
    createdAt: hoursAgo(9),
    updatedAt: hoursAgo(5),
  },
  {
    id: 'd15e8f70-3a2c-4b91-9e64-7c0a2d5f8b13',
    queryId: 'c0a7e542-6b19-4d83-a2f7-5e8c1d9b6043',
    conversationId: '7b4e2a90-8f13-4c65-9d20-1a6c8e3f5b72',
    sourceMessageId: '4f8a1c63-9d25-4b70-8e51-2c7a0f6d9b34',
    source: 'user_feedback',
    status: 'open',
    rawQuestion: 'Как вернуть предоплату за анализ, если передумал?',
    resolvedQuery: 'Возврат предоплаты за лабораторное исследование',
    reason: 'no_knowledge_base_answer',
    answerabilityReason:
      'В БЗ описан порядок оплаты, но нет порядка возврата предоплаты за лабораторное исследование.',
    sourceIds: [],
    feedback: {
      id: '5a1d7e93-2c48-4f60-b9a3-8e0c5d1f7a26',
      rating: 'negative',
      comment: 'Нашла только общую инструкцию по оплате, про возврат ничего нет.',
      reasonCode: 'no_knowledge_base_answer',
    },
    ownerComment: '',
    webSearchUsed: false,
    createdAt: hoursAgo(27),
    updatedAt: hoursAgo(19),
  },
  {
    id: '9c4a7e21-6d38-4f05-b1a7-2e8c9d0f4a56',
    queryId: 'e91b4d76-3a58-4c20-8f14-6d9a2e7b0c35',
    conversationId: '2d6f8a14-5c93-4b07-a8e2-9f1d3c6b5a40',
    sourceMessageId: '71c9e3a5-4b86-4d02-9f30-6a8e1c5b7d24',
    source: 'automatic',
    status: 'in_review',
    rawQuestion: 'Нужна ли справка для бассейна после 40 лет?',
    resolvedQuery: 'Справка для посещения бассейна: возрастные требования',
    reason: 'knowledge_outdated',
    answerabilityReason:
      'Найден документ 2021 года со ссылкой на отменённый приказ; актуальные требования не подтверждены.',
    confidence: 0.79,
    sourceIds: [
      {
        id: 'kb-swim-31',
        title: 'Справки для бассейна (редакция 2021)',
      },
    ],
    ownerComment: '',
    webSearchUsed: false,
    createdAt: hoursAgo(72),
    updatedAt: hoursAgo(26),
  },
  {
    id: 'e62b1d94-8f57-4c3a-a0d8-5b7e1f9c2d37',
    queryId: 'a4d8c216-9e73-4b50-8f61-3c0a7d5e2b98',
    conversationId: '9e3b6d80-1a47-4c25-b9f3-8d0e2a7c5b61',
    sourceMessageId: '38f5a9c2-7d14-4e60-b3a8-9c1f6e0d4b72',
    source: 'user_feedback',
    status: 'in_review',
    rawQuestion: 'Можно ли пить воду перед УЗИ брюшной полости?',
    resolvedQuery: 'Подготовка к УЗИ брюшной полости: можно ли пить воду',
    reason: 'knowledge_conflict',
    answerabilityReason:
      'Два источника противоречат друг другу: один разрешает воду за 2 часа, другой запрещает питьё за 6 часов.',
    confidence: 0.83,
    sourceIds: [
      {
        id: 'kb-ultrasound-12',
        title: 'Подготовка к УЗИ брюшной полости',
      },
      {
        id: 'kb-ultrasound-47',
        title: 'УЗИ органов брюшной полости: памятка',
      },
    ],
    feedback: {
      id: 'b8e4c1d7-6a29-4f53-8c70-2d9e5a1b3f64',
      rating: 'negative',
      comment:
        'В одной статье разрешают воду, в другой запрещают — непонятно, какому источнику верить.',
      reasonCode: 'knowledge_conflict',
    },
    ownerComment: 'Нужно сверить с протоколом отделения УЗИ и обновить обе памятки.',
    webSearchUsed: false,
    createdAt: hoursAgo(96),
    updatedAt: hoursAgo(10),
  },
  {
    id: '47f0a8c3-9b16-4e72-8c45-1a3d6f2b9e80',
    queryId: 'f2c5a8d1-4b96-4e37-a0c8-7d2f1b6e9a53',
    conversationId: 'c7a1e4b8-3d62-4f09-8b57-6e0d2c9a1f45',
    sourceMessageId: '0e6b3d97-8c14-4a52-b7f9-5d1a8e4c2b60',
    source: 'automatic',
    status: 'resolved',
    rawQuestion: 'Где получить результаты ПЦР-теста на COVID-19?',
    resolvedQuery: 'Выдача результатов ПЦР-теста на COVID-19',
    reason: 'no_knowledge_base_answer',
    answerabilityReason: 'В БЗ не было раздела о выдаче результатов ПЦР-тестов.',
    confidence: 0.94,
    sourceIds: [],
    ownerComment: 'Добавлена статья «Выдача результатов лабораторных исследований».',
    webSearchUsed: false,
    createdAt: hoursAgo(96),
    updatedAt: hoursAgo(28.8),
    resolvedAt: hoursAgo(28.8),
    resolvedBy: 'Смирнова Е.В.',
  },
  {
    id: 'a8d3c510-4e27-4b96-91f0-6c2e8a7d3f45',
    queryId: '5b9d2f64-8a17-4c30-9e52-1f7b4a0c6d83',
    conversationId: 'e4a8c1f6-2b95-4d73-8a06-3c9e7f1b5d28',
    sourceMessageId: '97c2e5a1-6d48-4b13-8f70-2a5c9e0d7b36',
    source: 'user_feedback',
    status: 'resolved',
    rawQuestion: 'Какие документы нужны для плановой госпитализации по ОМС?',
    resolvedQuery: 'Документы для плановой госпитализации по ОМС',
    reason: 'knowledge_incomplete',
    answerabilityReason:
      'В памятке перечислены только паспорт и полис, нет направления и результатов анализов.',
    sourceIds: [
      {
        id: 'kb-hospital-77',
        title: 'Плановая госпитализация: памятка пациенту',
      },
    ],
    feedback: {
      id: 'c1f8a3e5-9d26-4b70-8a14-6e3c2d5f9b07',
      rating: 'negative',
      comment: 'Не хватает направления и списка анализов.',
      reasonCode: 'knowledge_incomplete',
    },
    ownerComment: 'Памятка дополнена, добавлен чек-лист документов.',
    webSearchUsed: false,
    createdAt: hoursAgo(120),
    updatedAt: hoursAgo(36),
    resolvedAt: hoursAgo(36),
    resolvedBy: 'Смирнова Е.В.',
  },
  {
    id: '2e9f6b14-7c08-4d3a-b5e1-9a4f0c8d7b62',
    queryId: 'd6b3a719-5c82-4f04-9a61-8e2d7c1b5f39',
    conversationId: '6c0e4a97-1f58-4d23-b8a5-2e9c7f3d6b10',
    sourceMessageId: '1b7a9e35-4c68-4f20-8d91-5e3c0b6a2d74',
    source: 'automatic',
    status: 'dismissed',
    rawQuestion: 'Есть ли парковка для инвалидов у корпуса?',
    resolvedQuery: 'Парковка для инвалидов на территории ГКБ № 12',
    reason: 'no_knowledge_base_answer',
    answerabilityReason:
      'В БЗ нет схемы парковки; вопрос относится к административно-хозяйственной службе.',
    sourceIds: [],
    ownerComment: 'Вне зоны ответственности БЗ: вопрос передан в АХО.',
    webSearchUsed: false,
    createdAt: hoursAgo(144),
    updatedAt: hoursAgo(48),
    resolvedAt: hoursAgo(48),
    resolvedBy: 'Смирнова Е.В.',
  },
];

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
