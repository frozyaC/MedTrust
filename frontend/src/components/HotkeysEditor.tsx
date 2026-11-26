import { useState } from 'react';
import type { FC, KeyboardEvent } from 'react';
import { Keyboard, RotateCcw, X } from 'lucide-react';
import {
  DEFAULT_HOTKEYS,
  formatHotkey,
  HOTKEY_IDS,
  HOTKEY_LABELS,
  isReservedNavigationHotkey,
  Hotkey,
  HotkeyId,
  HotkeysConfig,
} from '../data/hotkeys';

interface HotkeysEditorProps {
  config: HotkeysConfig;
  onSave: (config: HotkeysConfig) => void;
  onClose: () => void;
}

export const HotkeysEditor: FC<HotkeysEditorProps> = ({
  config,
  onSave,
  onClose,
}) => {
  const [draft, setDraft] = useState<HotkeysConfig>(config);
  const [recording, setRecording] = useState<HotkeyId | null>(null);
  const [error, setError] = useState('');

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!recording) return;

    event.preventDefault();
    event.stopPropagation();

    if (['Alt', 'Control', 'Shift', 'Meta'].includes(event.key)) return;

    if (event.key === 'Escape') {
      setRecording(null);
      setError('');
      return;
    }

    const nextHotkey: Hotkey = {
      code: event.code,
      alt: event.altKey,
      ctrl: event.ctrlKey,
      shift: event.shiftKey,
      meta: event.metaKey,
    };

    if (
      ['Tab', 'CapsLock', 'Backspace', 'Delete'].includes(event.key) ||
      !event.code
    ) {
      setError('Выберите обычную клавишу или комбинацию клавиш.');
      return;
    }

    if (isReservedNavigationHotkey(nextHotkey)) {
      setError('↑, ↓ и Enter используются для навигации. Добавьте Alt, Ctrl, Shift или Meta.');
      return;
    }

    const conflict = HOTKEY_IDS.find(
      (id) =>
        id !== recording &&
        formatHotkey(draft[id]) === formatHotkey(nextHotkey),
    );

    if (conflict) {
      setError(`Эта комбинация уже назначена: ${HOTKEY_LABELS[conflict]}.`);
      return;
    }

    setDraft((current) => ({
      ...current,
      [recording]: nextHotkey,
    }));

    setRecording(null);
    setError('');
  };

  const resetDefaults = () => {
    setDraft(DEFAULT_HOTKEYS);
    setRecording(null);
    setError('');
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hotkeys-title"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
    >
      <div className="w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl bg-white shadow-2xl border border-[#BFDBFE]">
        <div className="flex items-center justify-between border-b border-[#EFF6FF] px-5 py-4">
          <div className="flex items-center gap-2">
            <Keyboard className="w-5 h-5 text-[#2563EB]" />
            <h2 id="hotkeys-title" className="text-base font-semibold text-[#0F172A]">
              Настройка горячих клавиш
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
            aria-label="Закрыть"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3 p-5">
          <p className="text-xs text-slate-500">
            Нажмите «Изменить», затем нажмите желаемую комбинацию на клавиатуре.
            Для отмены записи нажмите Esc.
          </p>

          {HOTKEY_IDS.map((id) => (
            <div
              key={id}
              className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2.5"
            >
              <span className="text-sm text-slate-700">{HOTKEY_LABELS[id]}</span>

              <div className="flex shrink-0 items-center gap-2">
                <kbd className="min-w-[90px] rounded-md border border-[#BFDBFE] bg-[#EFF6FF] px-2 py-1.5 text-center text-xs font-semibold text-[#2563EB]">
                  {recording === id ? 'Нажмите клавиши…' : formatHotkey(draft[id])}
                </kbd>

                <button
                  type="button"
                  onClick={() => {
                    setRecording(id);
                    setError('');
                  }}
                  className="rounded-lg border border-[#BFDBFE] px-3 py-1.5 text-xs font-semibold text-[#2563EB] hover:bg-[#EFF6FF]"
                >
                  {recording === id ? 'Ожидание…' : 'Изменить'}
                </button>
              </div>
            </div>
          ))}

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {error}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[#EFF6FF] px-5 py-4">
          <button
            type="button"
            onClick={resetDefaults}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Сбросить по умолчанию
          </button>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => onSave(draft)}
              disabled={recording !== null}
              className="rounded-lg bg-[#2563EB] px-4 py-2 text-xs font-semibold text-white hover:bg-[#1D4ED8] disabled:opacity-50"
            >
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
