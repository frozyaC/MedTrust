import { Patient, AnswerData } from '../types';

export const MOCK_PATIENTS: Patient[] = [
  {
    id: 'crm-1001',
    name: 'Иванова Анна Петровна',
    age: 34,
    sex: 'Ж',
    allergies: ['пенициллин'],
    chronic: [],
    contraindications: [],
    lastVisit: '12.05.2025',
  },
  {
    id: 'crm-1002',
    name: 'Петров Иван Ильич',
    age: 58,
    sex: 'М',
    allergies: [],
    chronic: ['гипертония'],
    contraindications: ['НПВС'],
    lastVisit: '04.04.2025',
  },
  {
    id: 'crm-1003',
    name: 'Смирнова Ольга Викторовна',
    age: 27,
    sex: 'Ж',
    allergies: [],
    chronic: [],
    contraindications: ['беременность 12 недель'],
    lastVisit: '18.01.2025',
  },
];

export const MOCK_ANSWERS: Record<string, AnswerData> = {
  gastro: {
    question: 'Как подготовиться к гастроскопии?',
    timestamp: '14:32',
    sections: [
      {
        key: 'summary',
        title: 'Кратко',
        text: 'За 6–8 часов до процедуры нельзя есть, за 2 часа — пить.',
        citations: ['W1'],
      },
      {
        key: 'prep',
        title: 'Подготовка',
        text: 'Утром не завтракать. Можно пить негазированную воду в небольшом объёме за 2 часа до исследования.',
        citations: ['W2'],
      },
      {
        key: 'important',
        title: 'Важно',
        text: 'У пациента указана аллергия на пенициллин — обязательно сообщить врачу-эндоскописту перед началом процедуры.',
        citations: ['W1', 'W2'],
      },
      {
        key: 'contraindications',
        title: 'Противопоказания',
        text: 'При наличии хронических патологий или беременности — требуется предварительное согласование с гастроэнтерологом.',
        citations: ['W2'],
      },
    ],
    sources: [
      {
        id: 'W1',
        sourceType: 'wiki',
        usedInAnswer: true,
        title: 'Подготовка к гастроскопии — wiki.js',
        wikiDate: 'обновлено 12.03.2024',
        quote: 'За 6–8 часов до исследования исключить приём пищи. При наличии аллергических реакций в анамнезе проинформировать медперсонал.',
        url: 'https://wiki.clinic.local/prep/gastroscopy',
      },
      {
        id: 'W2',
        sourceType: 'wiki',
        usedInAnswer: true,
        title: 'Клинические рекомендации по ЭГДС — wiki.js',
        wikiDate: 'обновлено 01.02.2024',
        quote: 'Пациентам с аллергией на пенициллин необходимо сообщить врачу для корректировки премедикации и местного обезболивания.',
        url: 'https://wiki.clinic.local/guidelines/egds',
      },
    ],
  },
};