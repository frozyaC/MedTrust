import {
  AlertTriangle,
  BookOpen,
  LayoutDashboard,
  LogOut,
  Map,
  MessageSquare,
  Settings,
  Sparkles,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { AdminRole } from '../../types/knowledgeGaps';
import { DEMO_ADMIN_USER, DEMO_DEVELOPER_USER } from '../../data/knowledgeGaps';

interface AdminSidebarProps {
  role: AdminRole;
  gapCount: number;
  onNavigate: (label: string) => void;
  onLogout?: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  count?: string;
  badge?: string;
  active?: boolean;
  disabled?: boolean;
}

const MAIN_NAV: NavItem[] = [
  { id: 'dialogs', label: 'Диалоги', icon: MessageSquare, count: '128' },
  { id: 'knowledge', label: 'База знаний', icon: BookOpen, count: '12 430' },
  { id: 'gaps', label: 'Карта пробелов', icon: Map, active: true },
  {
    id: 'quality',
    label: 'Проблемы качества',
    icon: AlertTriangle,
    badge: 'позже',
    disabled: true,
  },
];

export function AdminSidebar({ role, gapCount, onNavigate, onLogout }: AdminSidebarProps) {
  const user = role === 'developer' ? DEMO_DEVELOPER_USER : DEMO_ADMIN_USER;

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-r border-med-border bg-med-sidebar">
      <div className="border-b border-med-border px-4 py-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-med-text-muted">
          <LayoutDashboard className="h-4 w-4 text-med-primary" />
          Админ-панель
        </div>
        <p className="mt-1 text-sm text-med-text-secondary">ГКБ № 12 · база знаний</p>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-4" aria-label="Разделы админки">
        <div className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-med-text-muted">
          Рабочие разделы
        </div>

        <div className="space-y-1">
          {MAIN_NAV.map((item) => {
            const Icon = item.icon;
            const count = item.id === 'gaps' ? String(gapCount) : item.count;

            return (
              <button
                key={item.id}
                type="button"
                disabled={item.disabled}
                aria-current={item.active ? 'page' : undefined}
                onClick={() => {
                  if (!item.active && !item.disabled) onNavigate(item.label);
                }}
                className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  item.active
                    ? 'border border-med-border-strong bg-med-primary-light font-semibold text-med-primary shadow-med-card'
                    : item.disabled
                      ? 'cursor-not-allowed text-med-text-muted opacity-70'
                      : 'text-med-text-secondary hover:bg-med-surface/70 hover:text-med-text-primary'
                }`}
              >
                <Icon
                  className={`h-[18px] w-[18px] shrink-0 ${
                    item.active
                      ? 'text-med-primary'
                      : item.disabled
                        ? 'text-med-text-muted'
                        : 'text-med-text-secondary group-hover:text-med-primary'
                  }`}
                />
                <span className="min-w-0 flex-1 text-left">{item.label}</span>

                {item.badge && (
                  <span className="rounded-full border border-med-border bg-med-surface px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-med-text-muted">
                    {item.badge}
                  </span>
                )}
                {!item.badge && count && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      item.active
                        ? 'bg-med-surface text-med-primary'
                        : 'bg-med-surface/80 text-med-text-muted'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="my-4 border-t border-med-border" />

        <div className="space-y-1">
          <button
            type="button"
            onClick={() => onNavigate('Настройки')}
            className="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-med-text-secondary transition-colors hover:bg-med-surface/70 hover:text-med-text-primary"
          >
            <Settings className="h-[18px] w-[18px] shrink-0 text-med-text-secondary group-hover:text-med-primary" />
            <span>Настройки</span>
          </button>
        </div>

        <div className="mt-5 rounded-xl border border-med-border bg-med-surface/70 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-med-primary">
            <Sparkles className="h-4 w-4" />
            MVP
          </div>
          <p className="mt-1 text-xs leading-4 text-med-text-secondary">
            Только пробелы БЗ. Проблемы качества, Wiki.js и экспорт — в следующей итерации.
          </p>
        </div>
      </nav>

      <div className="mt-auto border-t border-med-border bg-med-sidebar/95 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 border-med-border-strong bg-med-primary-light text-xs font-bold text-med-primary">
            {user.avatar}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-med-text-primary">{user.name}</div>
            <div className="truncate text-xs text-med-text-muted">{user.roleShort}</div>
          </div>
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-error/10 hover:text-med-error"
              title="Выйти"
              aria-label="Выйти"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
