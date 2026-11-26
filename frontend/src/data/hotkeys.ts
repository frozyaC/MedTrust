export type HotkeyId =
  | 'focusPatient'
  | 'focusQuestion'
  | 'newConversation'
  | 'resetPatient'
  | `template${number}`;

export interface Hotkey {
  code: string;
  alt: boolean;
  ctrl: boolean;
  shift: boolean;
  meta: boolean;
}

export type HotkeysConfig = Record<HotkeyId, Hotkey>;

export const HOTKEYS_STORAGE_KEY = 'medtrust.hotkeys';

export const DEFAULT_HOTKEYS: HotkeysConfig = {
  focusPatient: { code: 'KeyZ', alt: true, ctrl: false, shift: false, meta: false },
  focusQuestion: { code: 'KeyX', alt: true, ctrl: false, shift: false, meta: false },
  newConversation: { code: 'KeyQ', alt: true, ctrl: false, shift: false, meta: false },
  resetPatient: { code: 'KeyR', alt: true, ctrl: false, shift: false, meta: false },

  template1: { code: 'Digit1', alt: true, ctrl: false, shift: false, meta: false },
  template2: { code: 'Digit2', alt: true, ctrl: false, shift: false, meta: false },
  template3: { code: 'Digit3', alt: true, ctrl: false, shift: false, meta: false },
  template4: { code: 'Digit4', alt: true, ctrl: false, shift: false, meta: false },
  template5: { code: 'Digit5', alt: true, ctrl: false, shift: false, meta: false },
  template6: { code: 'Digit6', alt: true, ctrl: false, shift: false, meta: false },
  template7: { code: 'Digit7', alt: true, ctrl: false, shift: false, meta: false },
  template8: { code: 'Digit8', alt: true, ctrl: false, shift: false, meta: false },
  template9: { code: 'Digit9', alt: true, ctrl: false, shift: false, meta: false },
};

export const HOTKEY_LABELS: Record<HotkeyId, string> = {
  focusPatient: 'Фокус на поиске пациента',
  focusQuestion: 'Фокус на поле вопроса',
  newConversation: 'Начать новый диалог',
  resetPatient: 'Сбросить выбранного пациента',
  template1: 'Шаблон вопроса / уточнения 1',
  template2: 'Шаблон вопроса / уточнения 2',
  template3: 'Шаблон вопроса / уточнения 3',
  template4: 'Шаблон вопроса / уточнения 4',
  template5: 'Шаблон вопроса / уточнения 5',
  template6: 'Шаблон вопроса / уточнения 6',
  template7: 'Шаблон вопроса / уточнения 7',
  template8: 'Шаблон вопроса / уточнения 8',
  template9: 'Шаблон вопроса / уточнения 9',
};

export const HOTKEY_IDS = Object.keys(DEFAULT_HOTKEYS) as HotkeyId[];

export function loadHotkeys(): HotkeysConfig {
  try {
    const raw = window.localStorage.getItem(HOTKEYS_STORAGE_KEY);
    if (!raw) return DEFAULT_HOTKEYS;

    const parsed = JSON.parse(raw) as Partial<HotkeysConfig>;

    return Object.fromEntries(
      HOTKEY_IDS.map((id) => {
        const saved = parsed[id];
        const valid =
          saved &&
          typeof saved.code === 'string' &&
          typeof saved.alt === 'boolean' &&
          typeof saved.ctrl === 'boolean' &&
          typeof saved.shift === 'boolean' &&
          typeof saved.meta === 'boolean';

        return [id, valid ? saved : DEFAULT_HOTKEYS[id]];
      }),
    ) as HotkeysConfig;
  } catch {
    return DEFAULT_HOTKEYS;
  }
}

export function saveHotkeys(config: HotkeysConfig) {
  window.localStorage.setItem(HOTKEYS_STORAGE_KEY, JSON.stringify(config));
}

export function matchesHotkey(event: KeyboardEvent, hotkey: Hotkey) {
  return (
    event.code === hotkey.code &&
    event.altKey === hotkey.alt &&
    event.ctrlKey === hotkey.ctrl &&
    event.shiftKey === hotkey.shift &&
    event.metaKey === hotkey.meta
  );
}

export function formatHotkey(hotkey: Hotkey): string {
  const parts: string[] = [];

  if (hotkey.ctrl) parts.push('Ctrl');
  if (hotkey.alt) parts.push('Alt');
  if (hotkey.shift) parts.push('Shift');
  if (hotkey.meta) parts.push('Meta');

  const codeLabels: Record<string, string> = {
    Escape: 'Esc',
    Space: 'Пробел',
    Enter: 'Enter',
    Backspace: 'Backspace',
    Tab: 'Tab',
    ArrowUp: '↑',
    ArrowDown: '↓',
    ArrowLeft: '←',
    ArrowRight: '→',
    Minus: '-',
    Equal: '=',
    BracketLeft: '[',
    BracketRight: ']',
    Semicolon: ';',
    Quote: "'",
    Comma: ',',
    Period: '.',
    Slash: '/',
    Backslash: '\\',
  };

  let key = codeLabels[hotkey.code];

  if (!key && hotkey.code.startsWith('Key')) {
    key = hotkey.code.slice(3);
  }
  if (!key && hotkey.code.startsWith('Digit')) {
    key = hotkey.code.slice(5);
  }
  if (!key && hotkey.code.startsWith('Numpad')) {
    key = `Num ${hotkey.code.slice(6)}`;
  }

  parts.push(key ?? hotkey.code);
  return parts.join(' + ');
}