import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, HelpCircle, LogOut } from 'lucide-react';
import { AdminRole } from '../../types/knowledgeGaps';
import { DEMO_ADMIN_USER, DEMO_DEVELOPER_USER } from '../../data/knowledgeGaps';

interface AdminHeaderProps {
  role: AdminRole;
  onRoleChange: (role: AdminRole) => void;
  onLogout?: () => void;
}

const ROLE_OPTIONS: Array<{
  value: AdminRole;
  label: string;
  description: string;
}> = [
  {
    value: 'kb_owner',
    label: 'Владелец БЗ',
    description: 'Заведующий регистратурой',
  },
  {
    value: 'developer',
    label: 'Разработчик',
    description: 'Технический вид без персональных данных',
  },
];

export function AdminHeader({ role, onRoleChange, onLogout }: AdminHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const user = role === 'developer' ? DEMO_DEVELOPER_USER : DEMO_ADMIN_USER;

  useEffect(() => {
    if (!menuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

  return (
    <header className="z-20 flex h-16 shrink-0 select-none items-center justify-between border-b border-med-border bg-med-surface px-6 shadow-med-card">
      <div className="flex min-w-0 items-center gap-5">
        <div className="flex items-center gap-2.5">
          <img src="/medtrust.png" alt="MedTrust" className="h-9 w-9 rounded-xl object-contain" />
          <span className="text-xl font-bold tracking-tight">
            <span className="text-med-text-primary">Med</span>
            <span className="text-med-primary">Trust</span>
          </span>
        </div>

        <div className="h-5 w-px bg-med-border" />

        <span className="whitespace-nowrap text-sm font-semibold text-med-text-primary">ГКБ № 12</span>

        <div className="hidden items-center gap-2 lg:flex">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-med-success/30 bg-med-success/10 px-2.5 py-1 text-xs font-medium text-med-text-primary">
            <span className="h-2 w-2 rounded-full bg-med-success" />
            <span>CRM: подключена</span>
          </div>

          <div className="inline-flex items-center gap-1.5 rounded-full border border-med-border-strong bg-med-primary-light px-2.5 py-1 text-xs font-medium text-med-primary-hover">
            <span className="h-2 w-2 rounded-full bg-med-primary" />
            <span>wiki.js: 12 430 статей</span>
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-right transition-colors hover:bg-med-bg"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            title="Переключить демо-роль"
          >
            <div>
              <div className="text-xs font-medium text-med-text-muted">{user.role}</div>
              <div className="text-sm font-semibold text-med-text-primary">{user.name}</div>
            </div>
            <ChevronDown
              className={`h-4 w-4 text-med-text-secondary transition-transform ${
                menuOpen ? 'rotate-180' : ''
              }`}
            />
          </button>

          {menuOpen && (
            <div
              className="absolute right-0 top-full z-50 mt-2 w-[300px] animate-fade-in rounded-xl border border-med-border bg-med-surface p-1.5 shadow-med-panel"
              role="menu"
            >
              <div className="px-2.5 py-2 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                Демо-роль
              </div>
              {ROLE_OPTIONS.map((option) => {
                const active = option.value === role;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    onClick={() => {
                      onRoleChange(option.value);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors ${
                      active ? 'bg-med-primary-light/60' : 'hover:bg-med-bg'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-med-text-primary">{option.label}</div>
                      <div className="text-xs text-med-text-secondary">{option.description}</div>
                    </div>
                    {active && <Check className="h-4 w-4 shrink-0 text-med-primary" />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <button
          type="button"
          className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-primary"
          title="Справка и поддержка"
          aria-label="Справка и поддержка"
        >
          <HelpCircle className="h-5 w-5" />
        </button>

        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-error/10 hover:text-med-error"
            title="Выйти из аккаунта"
            aria-label="Выйти из аккаунта"
          >
            <LogOut className="h-5 w-5" />
          </button>
        )}

        <div className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-med-border-strong bg-med-primary-light text-sm font-bold text-med-primary shadow-med-card">
          {user.avatar}
        </div>
      </div>
    </header>
  );
}
