import React, { useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { SearchBar } from './components/SearchBar';
import { AnswerBlock } from './components/AnswerBlock';
import { SourceCard } from './components/SourceCard';
import { FeedbackBar } from './components/FeedbackBar';
import { StateSelector } from './components/StateSelector';
import { Toast } from './components/Toast';
import { MOCK_PATIENTS, MOCK_ANSWERS } from './data/mockData';
import { Patient, ScreenState, AnswerData } from './types';
import { 
  Search, 
  AlertOctagon, 
  RefreshCw, 
  Sparkles, 
  FileQuestion,
  Info
} from 'lucide-react';

export default function App() {
  const [patients] = useState<Patient[]>(MOCK_PATIENTS);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(MOCK_PATIENTS[0]);
  const [screenState, setScreenState] = useState<ScreenState>('answer');
  const [currentAnswer, setCurrentAnswer] = useState<AnswerData>(MOCK_ANSWERS.gastro);
  const [highlightedSourceId, setHighlightedSourceId] = useState<number | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Handle selecting patient from sidebar or search bar
  const handleSelectPatient = (patient: Patient | null) => {
    setSelectedPatient(patient);
    if (!patient && screenState === 'ready') {
      setScreenState('empty');
    } else if (patient && screenState === 'empty') {
      setScreenState('ready');
    }
    if (patient) {
      setToastMessage(`Выбран пациент: ${patient.name}`);
    }
  };

  // Handle question submit
  const handleAskQuestion = (query: string) => {
    setScreenState('loading');
    setTimeout(() => {
      // Create answer response
      const answer: AnswerData = {
        question: query,
        timestamp: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        sections: [
          {
            key: 'summary',
            title: 'Кратко',
            text: 'За 6–8 часов до процедуры нельзя есть, за 2 часа — пить. [1]',
            citations: [1],
          },
          {
            key: 'prep',
            title: 'Подготовка',
            text: 'Утром не завтракать. Можно пить воду. [2]',
            citations: [2],
          },
          {
            key: 'important',
            title: 'Важно',
            text: selectedPatient?.allergies.length 
              ? `У пациента указана аллергия на ${selectedPatient.allergies.join(', ')} — сообщить врачу. [1][2]`
              : 'При заполнении медкарты проверить аллергоанамнез. [1]',
            citations: [1, 2],
          },
          {
            key: 'contraindications',
            title: 'Противопоказания',
            text: selectedPatient?.contraindications.length
              ? `У пациента противопоказания: ${selectedPatient.contraindications.join(', ')} — уточнить у профильного специалиста. [2]`
              : 'При беременности — уточнить у гастроэнтеролога. [2]',
            citations: [2],
          },
        ],
        sources: [
          {
            id: 1,
            title: 'Подготовка к гастроскопии — wiki.js',
            wikiDate: 'обновлено 12.03.2024',
            quote: 'За 6–8 часов до исследования исключить приём пищи...',
            url: 'https://wiki.clinic.local/prep/gastroscopy',
          },
          {
            id: 2,
            title: 'Клинические рекомендации по ЭГДС — wiki.js',
            wikiDate: 'обновлено 01.02.2024',
            quote: 'Пациентам с аллергией на пенициллин необходимо сообщить...',
            url: 'https://wiki.clinic.local/guidelines/egds',
          },
        ],
      };

      setCurrentAnswer(answer);
      setScreenState('answer');
    }, 1200);
  };

  // Scroll to citation source card
  const handleCitationClick = (citationId: number) => {
    setHighlightedSourceId(citationId);
    const element = document.getElementById(`source-${citationId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setTimeout(() => setHighlightedSourceId(null), 2500);
  };

  // Feedback action handler
  const handleFeedback = (type: 'useful' | 'useless' | 'not_found' | 'copy') => {
    if (type === 'not_found') {
      setToastMessage('Спасибо! Вопрос зафиксирован, заведующий регистратурой получит уведомление.');
    } else if (type === 'useful') {
      setToastMessage('Спасибо за отзыв! Отметка "Полезно" сохранена.');
    } else if (type === 'useless') {
      setToastMessage('Спасибо за отзыв! Отметка зафиксирована.');
    } else if (type === 'copy') {
      setToastMessage('Текст ответа скопирован в буфер обмена.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#EFF6FF] text-[#0F172A] font-sans antialiased overflow-hidden">
      {/* Header */}
      <Header />

      {/* State Switcher Bar for testing all states */}
      <StateSelector
        currentState={screenState}
        onSelectState={(state) => {
          setScreenState(state);
          if (state === 'empty') setSelectedPatient(null);
          if (state === 'ready' && !selectedPatient) setSelectedPatient(MOCK_PATIENTS[0]);
        }}
      />

      {/* Main App Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          patients={patients}
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
        />

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6 space-y-4 max-w-[1120px] mx-auto">
          {/* Search Bar Component */}
          <SearchBar
            selectedPatient={selectedPatient}
            onAsk={handleAskQuestion}
            onSelectPatientClick={() => {
              if (selectedPatient) {
                setSelectedPatient(null);
              } else {
                setSelectedPatient(patients[0]);
                if (screenState === 'empty') setScreenState('ready');
              }
            }}
            isLoading={screenState === 'loading'}
          />

          {/* Render content based on screen state */}
          {screenState === 'empty' && (
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
          )}

          {screenState === 'ready' && (
            <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs space-y-4">
              <div className="flex items-center gap-3 text-[#2563EB]">
                <Sparkles className="w-6 h-6" />
                <h3 className="font-semibold text-base text-[#0F172A]">
                  Готов к поиску в базе знаний wiki.js
                </h3>
              </div>
              <p className="text-xs text-[#475569]">
                Введите вопрос в строку выше. Вы также можете выкатывать популярные запросы:
              </p>
              <div className="flex flex-wrap gap-2 pt-2">
                {[
                  'Как подготовиться к гастроскопии?',
                  'Правила сдачи крови натощак',
                  'Противопоказания к МРТ головного мозга',
                  'Документы для первичного приёма',
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleAskQuestion(preset)}
                    className="px-3 py-2 bg-[#EFF6FF] hover:bg-[#DBEAFE] text-[#2563EB] border border-[#BFDBFE] text-xs font-medium rounded-lg transition-colors text-left"
                  >
                    + {preset}
                  </button>
                ))}
              </div>
            </div>
          )}

          {screenState === 'loading' && (
            <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs space-y-6 max-w-[800px] animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
                <span className="font-semibold text-sm text-[#2563EB]">
                  Ищем в базе знаний...
                </span>
              </div>
              <div className="space-y-3">
                <div className="h-4 bg-[#DBEAFE] rounded w-1/4" />
                <div className="h-3 bg-slate-100 rounded w-full" />
                <div className="h-3 bg-slate-100 rounded w-5/6" />
                <div className="h-4 bg-[#DBEAFE] rounded w-1/3 mt-4" />
                <div className="h-3 bg-slate-100 rounded w-4/5" />
              </div>
            </div>
          )}

          {(screenState === 'answer' || screenState === 'conflict') && (
            <>
              {/* Answer block */}
              <AnswerBlock
                answer={currentAnswer}
                selectedPatient={selectedPatient}
                onCitationClick={handleCitationClick}
                conflictWarning={
                  screenState === 'conflict'
                    ? 'Обнаружено противоречие между источниками [1] и [2]. Уведомлён владелец базы знаний.'
                    : undefined
                }
                onViewConflictSources={() => handleCitationClick(1)}
              />

              {/* Sources block */}
              <SourceCard
                sources={currentAnswer.sources}
                highlightedId={highlightedSourceId}
              />

              {/* Feedback bar */}
              <FeedbackBar onFeedback={handleFeedback} />
            </>
          )}

          {screenState === 'no_answer' && (
            <div className="bg-white rounded-xl border border-[#BFDBFE] p-8 shadow-xs text-center max-w-[800px] space-y-4 my-4">
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
                onClick={() => {
                  setToastMessage('Вопрос отмечен как пробел в базе знаний.');
                }}
                className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg transition-colors shadow-xs"
              >
                Отметить как пробел
              </button>
            </div>
          )}

          {screenState === 'error' && (
            <div className="bg-white rounded-xl border border-red-200 p-8 shadow-xs text-center max-w-[800px] space-y-4 my-4">
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
                onClick={() => setScreenState('answer')}
                className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg transition-colors shadow-xs inline-flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Обновить</span>
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <Toast
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
