import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { SearchBar } from './components/SearchBar';
import { AnswerBlock } from './components/AnswerBlock';
import { FeedbackBar } from './components/FeedbackBar';
// import { StateSelector } from './components/StateSelector';
import { Toast } from './components/Toast';
import { ConversationHeader } from './components/ConversationHeader';
import { QuestionBubble } from './components/QuestionBubble';
import { SessionDivider } from './components/SessionDivider';
import { SourceGroup } from './components/SourceGroup';
import { SuggestionRow } from './components/SuggestionRow';
import { ChatComposer } from './components/ChatComposer';
import { AnswerSkeleton } from './components/AnswerSkeleton';
import { MessageThread } from './components/MessageThread';
import { MOCK_PATIENTS, MOCK_ANSWERS } from './data/mockData';
import {
  AnswerData,
  ConversationItem,
  FeedbackRating,
  Patient,
  ScreenState,
} from './types';
import { askAndBuildItem } from './api/query';
import {
  AlertOctagon,
  FileQuestion,
  RefreshCw,
  Search,
  Sparkles,
  UserCheck,
} from 'lucide-react';

type Threads = Record<string, ConversationItem[]>;

const UNASSIGNED_THREAD = 'unassigned';

const now = () =>
  new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

/**
 * Демонстрационный ответ. Используется только в режиме демонстрации
 * (кнопки StateSelector 4/6/8), чтобы показать UI без реального запроса.
 * В обычном потоке ответы приходят от бэка через `askAndBuildItem`.
 */
const makeDemoAnswer = (
  question: string,
  timestamp: string,
  patient: Patient | null,
  followUp: boolean,
): AnswerData => ({
  question,
  timestamp,
  sections: followUp
    ? [
        {
          key: 'summary',
          title: 'Кратко',
          text: question.toLowerCase().includes('зуб')
            ? 'Да, чистить зубы утром можно.'
            : 'Уточнение учтено вместе с предыдущими сообщениями диалога.',
          citations: [1],
        },
        {
          key: 'important',
          title: 'Важно',
          text: 'Не глотайте воду. Пить воду можно в небольшом объёме за 2 часа до исследования.',
          citations: [2],
        },
      ]
    : [
        {
          key: 'summary',
          title: 'Кратко',
          text: 'За 6–8 часов до процедуры нельзя есть, за 2 часа — пить.',
          citations: [1],
        },
        {
          key: 'prep',
          title: 'Подготовка',
          text: 'Утром не завтракать. Можно пить негазированную воду в небольшом объёме за 2 часа до исследования.',
          citations: [2],
        },
        {
          key: 'important',
          title: 'Важно',
          text: patient?.allergies.length
            ? `У пациента указана аллергия на ${patient.allergies.join(', ')} — обязательно сообщить врачу.`
            : 'При заполнении медкарты проверить аллергоанамнез.',
          citations: [1, 2],
        },
        {
          key: 'contraindications',
          title: 'Противопоказания',
          text: patient?.contraindications.length
            ? `У пациента противопоказания: ${patient.contraindications.join(', ')} — требуется согласование со специалистом.`
            : 'При беременности — уточнить у гастроэнтеролога.',
          citations: [2],
        },
      ],
  sources: MOCK_ANSWERS.gastro.sources,
});

const demoItem = (
  id: string,
  question: string,
  timestamp: string,
  status: ConversationItem['status'] = 'answer',
  followUp = false,
): ConversationItem => ({
  id,
  question,
  timestamp,
  status,
  answer:
    status === 'answer' || status === 'conflict'
      ? makeDemoAnswer(question, timestamp, MOCK_PATIENTS[0], followUp)
      : undefined,
  sourcesExpanded: followUp,
  feedback: null,
});

const oneAnswerThread = (): ConversationItem[] => [
  {
    ...demoItem('demo-answer-1', 'Как подготовиться к гастроскопии?', '14:32'),
    sourcesExpanded: true,
  },
];

const historyThread = (): ConversationItem[] => [
  {
    ...demoItem('demo-history-1', 'Как подготовиться к гастроскопии?', '14:32'),
    sourcesExpanded: false,
  },
  demoItem('demo-history-2', 'Можно ли утром чистить зубы?', '14:35', 'answer', true),
];

export default function App() {
  const [patients] = useState<Patient[]>(MOCK_PATIENTS);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(MOCK_PATIENTS[0]);
  const [screenState, setScreenState] = useState<ScreenState>('ready');
  const [threads, setThreads] = useState<Threads>({});
  const [highlightedSource, setHighlightedSource] = useState<{
    answerId: string;
    sourceId: number;
  } | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState('');
  const threadEndRef = useRef<HTMLDivElement>(null);

  const threadKey = selectedPatient?.id ?? UNASSIGNED_THREAD;
  const currentThread = threads[threadKey] ?? [];
  const hasThread = currentThread.length > 0;
  const latestItem = currentThread[currentThread.length - 1];
  const isLoading = latestItem?.status === 'loading';
  const latestCompleted = latestItem && latestItem.status !== 'loading';
  const messageCount = currentThread.length * 2;

  useEffect(() => {
    if (hasThread) {
      requestAnimationFrame(() => {
        threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      });
    }
  }, [currentThread.length, latestItem?.status, hasThread]);

  const setCurrentThread = (updater: (items: ConversationItem[]) => ConversationItem[]) => {
    setThreads((current) => ({
      ...current,
      [threadKey]: updater(current[threadKey] ?? []),
    }));
  };

  const handleSelectPatient = (patient: Patient | null) => {
    if (patient) {
      setThreads((current) => {
        const next = { ...current };
        delete next[UNASSIGNED_THREAD];
        return next;
      });
      setSelectedPatient(patient);
      const patientThread = threads[patient.id] ?? [];
      setScreenState(patientThread.length ? 'answer' : 'ready');
      setToastMessage(`Выбран пациент: ${patient.name}`);
      return;
    }
    setSelectedPatient(null);
    setScreenState(threads[UNASSIGNED_THREAD]?.length ? 'answer' : 'empty');
  };

  /**
   * Реальный запрос к бэку. Вместо setTimeout из Figma-версии —
   * вызов `askAndBuildItem`, который инкапсулирует fetch + маппинг + статус.
   */
  const handleAskQuestion = (query: string) => {
    const key = threadKey;
    const patient = selectedPatient;
    const id = `message-${Date.now()}`;
    const timestamp = now();

    const loadingItem: ConversationItem = {
      id,
      question: query,
      timestamp,
      status: 'loading',
      sourcesExpanded: false,
      feedback: null,
    };

    setThreads((current) => ({
      ...current,
      [key]: [
        ...(current[key] ?? []).map((item) => ({ ...item, sourcesExpanded: false })),
        loadingItem,
      ],
    }));
    setScreenState('loading');

    void askAndBuildItem(query, patient, id, timestamp).then((item) => {
      setThreads((current) => ({
        ...current,
        [key]: (current[key] ?? []).map((existing) =>
          existing.id === id ? { ...item, sourcesExpanded: true } : existing,
        ),
      }));
      setScreenState(
        item.status === 'no_answer'
          ? 'no_answer'
          : item.status === 'error'
            ? 'error'
            : 'answer',
      );
    });
  };

  const handleCitationClick = (answerId: string, sourceId: number) => {
    setCurrentThread((items) =>
      items.map((item) =>
        item.id === answerId ? { ...item, sourcesExpanded: true } : item,
      ),
    );
    setHighlightedSource({ answerId, sourceId });
    window.setTimeout(() => {
      document
        .getElementById(`source-${answerId}-${sourceId}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
    window.setTimeout(() => setHighlightedSource(null), 2500);
  };

  const handleFeedback = (
    itemId: string,
    type: 'useful' | 'useless' | 'not_found' | 'copy',
  ) => {
    if (type === 'useful' || type === 'useless') {
      setCurrentThread((items) =>
        items.map((item) =>
          item.id === itemId ? { ...item, feedback: type as FeedbackRating } : item,
        ),
      );
    }

    const messages = {
      useful: 'Спасибо за отзыв! Отметка "Полезно" сохранена.',
      useless: 'Спасибо за отзыв! Отметка зафиксирована.',
      not_found:
        'Спасибо! Вопрос зафиксирован, заведующий регистратурой получит уведомление.',
      copy: 'Текст ответа скопирован в буфер обмена.',
    };
    setToastMessage(messages[type]);
  };

  const clearConversation = () => {
    setThreads((current) => ({ ...current, [threadKey]: [] }));
    setScreenState(selectedPatient ? 'ready' : 'empty');
    setToastMessage('Диалог очищен. Можно задать новый вопрос.');
  };

  /**
   * Демо-режим для StateSelector. Использует `demoItem` / `makeDemoAnswer` —
   * локальные моки, не бэк. Реальные ответы идут только через `handleAskQuestion`.
   */
  const selectDemoState = (state: ScreenState) => {
    setScreenState(state);
    setHighlightedSource(null);

    if (state === 'empty') {
      setSelectedPatient(null);
      setThreads((current) => ({ ...current, [UNASSIGNED_THREAD]: [] }));
      return;
    }

    setSelectedPatient(MOCK_PATIENTS[0]);
    setThreads((current) => {
      const next = { ...current };
      delete next[UNASSIGNED_THREAD];

      if (state === 'ready') next['crm-1001'] = [];
      if (state === 'answer') next['crm-1001'] = oneAnswerThread();
      if (state === 'history') next['crm-1001'] = historyThread();
      if (state === 'loading') {
        next['crm-1001'] = [
          demoItem('demo-loading', 'Как подготовиться к гастроскопии?', '14:32', 'loading'),
        ];
      }
      if (state === 'no_answer' || state === 'error') {
        next['crm-1001'] = [
          demoItem(
            `demo-${state}`,
            'Как подготовиться к гастроскопии?',
            '14:32',
            state,
          ),
        ];
      }
      if (state === 'conflict') {
        next['crm-1001'] = [
          {
            ...demoItem(
              'demo-conflict',
              'Как подготовиться к гастроскопии?',
              '14:32',
              'conflict',
            ),
            sourcesExpanded: true,
          },
        ];
      }
      return next;
    });
  };

  const emptyContent = useMemo(
    () => (
      <div className="bg-white rounded-xl border border-[#BFDBFE] p-12 text-center shadow-xs flex flex-col items-center justify-center my-6 space-y-4">
        <div className="w-16 h-16 rounded-full bg-[#DBEAFE] flex items-center justify-center text-[#2563EB] shadow-xs">
          <Search className="w-8 h-8" />
        </div>
        <div className="space-y-1">
          <h3 className="font-semibold text-lg text-[#0F172A]">
            Выберите пациента и задайте вопрос
          </h3>
          <p className="text-xs text-[#475569] max-w-md">
            Выберите пациента в списке слева или задайте общий вопрос без персонализации.
          </p>
        </div>
        <button
          onClick={() => {
            setSelectedPatient(patients[0]);
            setScreenState('ready');
          }}
          className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg transition-colors shadow-xs"
        >
          Выбрать пациента
        </button>
      </div>
    ),
    [patients],
  );

  return (
    <div className="h-screen flex flex-col bg-[#EFF6FF] text-[#0F172A] font-sans antialiased overflow-hidden">
      <Header />
      {/* <StateSelector currentState={screenState} onSelectState={selectDemoState} /> */}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar
          patients={patients}
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
        />

        {!hasThread ? (
          <main className="flex-1 overflow-y-auto p-6 space-y-4 max-w-[1120px] mx-auto">
            <SearchBar
              selectedPatient={selectedPatient}
              onAsk={handleAskQuestion}
              onSelectPatientClick={() =>
                handleSelectPatient(selectedPatient ? null : patients[0])
              }
              isLoading={false}
            />

            {screenState === 'empty' && emptyContent}

            {screenState === 'ready' && (
              <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs space-y-4">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-[#DBEAFE] flex items-center justify-center text-[#2563EB] shrink-0">
                    <UserCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-base text-[#0F172A] mb-1">
                      Пациент выбран
                    </h3>
                    <p className="text-xs text-[#475569] leading-relaxed">
                      Задайте вопрос в строке выше. Ответ будет персонализирован с учётом данных
                      пациента из CRM.
                    </p>
                  </div>
                </div>
                <div className="pt-3 border-t border-[#EFF6FF]">
                  <div className="flex items-center gap-2 text-xs text-[#475569] mb-2">
                    <Sparkles className="w-3.5 h-3.5 text-[#3B82F6]" />
                    <span className="font-medium">Популярные вопросы</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      'Как подготовиться к гастроскопии?',
                      'Правила сдачи крови натощак',
                      'Противопоказания к МРТ головного мозга',
                      'Документы для первичного приёма',
                    ].map((preset) => (
                      <button
                        key={preset}
                        onClick={() => handleAskQuestion(preset)}
                        className="px-3 py-2 bg-[#EFF6FF] hover:bg-[#DBEAFE] text-[#2563EB] border border-[#BFDBFE] text-xs font-medium rounded-lg transition-colors text-left"
                      >
                        + {preset}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </main>
        ) : (
          <main className="flex-1 min-w-0 min-h-0 flex flex-col bg-[#EFF6FF]">
            <ConversationHeader
              patient={selectedPatient}
              messageCount={messageCount}
              onChangePatient={() =>
                handleSelectPatient(selectedPatient ? null : patients[0])
              }
              onNewConversation={clearConversation}
            />

            <MessageThread endRef={threadEndRef}>
              <SessionDivider />
              {currentThread.map((item, index) => (
                <div key={item.id} className="space-y-4">
                  <QuestionBubble text={item.question} time={item.timestamp} />

                  {item.status === 'loading' && <AnswerSkeleton />}

                  {(item.status === 'answer' || item.status === 'conflict') &&
                    item.answer && (
                      <>
                        <AnswerBlock
                          answer={item.answer}
                          selectedPatient={selectedPatient}
                          hideQuestion
                          considersHistory={index > 0}
                          onCitationClick={(sourceId) =>
                            handleCitationClick(item.id, sourceId)
                          }
                          conflictWarning={
                            item.status === 'conflict'
                              ? 'Обнаружено противоречие между источниками [1] и [2]. Уведомлён владелец базы знаний.'
                              : undefined
                          }
                          onViewConflictSources={() =>
                            handleCitationClick(item.id, 1)
                          }
                        />
                        <SourceGroup
                          answer={item.answer}
                          answerId={item.id}
                          expanded={item.sourcesExpanded}
                          highlightedId={
                            highlightedSource?.answerId === item.id
                              ? highlightedSource.sourceId
                              : null
                          }
                          onToggle={() =>
                            setCurrentThread((items) =>
                              items.map((candidate) =>
                                candidate.id === item.id
                                  ? {
                                      ...candidate,
                                      sourcesExpanded: !candidate.sourcesExpanded,
                                    }
                                  : candidate,
                              ),
                            )
                          }
                        />
                        {item.feedback ? (
                          <span className="inline-flex px-3 py-1.5 bg-white border border-[#BFDBFE] rounded-full text-xs text-[#475569]">
                            Оценка:{' '}
                            {item.feedback === 'useful' ? 'полезно' : 'бесполезно'}
                          </span>
                        ) : (
                          <FeedbackBar
                            onFeedback={(type) => handleFeedback(item.id, type)}
                          />
                        )}
                      </>
                    )}

                  {item.status === 'no_answer' && (
                    <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs text-center max-w-[800px] space-y-4">
                      <div className="w-12 h-12 rounded-full bg-amber-100 text-[#F59E0B] flex items-center justify-center mx-auto">
                        <FileQuestion className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <h3 className="font-semibold text-base text-[#0F172A]">
                          В базе знаний нет точного ответа
                        </h3>
                        <p className="text-xs text-[#475569]">
                          Мы отправили запрос заведующему регистратурой.
                        </p>
                      </div>
                      <button
                        onClick={() =>
                          setToastMessage('Вопрос отмечен как пробел в базе знаний.')
                        }
                        className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg transition-colors shadow-xs"
                      >
                        Отметить как пробел
                      </button>
                    </div>
                  )}

                  {item.status === 'error' && (
                    <div className="bg-white rounded-xl border border-red-200 p-8 shadow-xs text-center max-w-[800px] space-y-4">
                      <div className="w-12 h-12 rounded-full bg-red-100 text-[#EF4444] flex items-center justify-center mx-auto">
                        <AlertOctagon className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <h3 className="font-semibold text-base text-[#0F172A]">
                          Не удалось подключиться к wiki.js. Повторите позже.
                        </h3>
                        <p className="text-xs text-[#475569]">
                          Проверьте сетевое подключение к локальному серверу базы знаний.
                        </p>
                      </div>
                      <button
                        onClick={() => handleAskQuestion(item.question)}
                        className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg transition-colors shadow-xs inline-flex items-center gap-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Обновить</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </MessageThread>

            {latestCompleted && (
              <SuggestionRow
                onSelect={(value) => {
                  setSuggestion('');
                  window.setTimeout(() => setSuggestion(value), 0);
                }}
              />
            )}
            <ChatComposer
              isLoading={isLoading}
              suggestion={suggestion}
              onSend={handleAskQuestion}
            />
          </main>
        )}
      </div>

      {toastMessage && (
        <Toast message={toastMessage} onClose={() => setToastMessage(null)} />
      )}
    </div>
  );
}