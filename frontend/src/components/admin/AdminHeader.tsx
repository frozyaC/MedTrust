import { HelpCircle, LogOut, ArrowLeft } from 'lucide-react';
import { useAuth, userInitials, userRoleLabel } from '../../auth/AuthContext';

interface AdminHeaderProps {
  onLogout?: () => void;
}

export function AdminHeader({ onLogout }: AdminHeaderProps) {
  const { user } = useAuth();
  if (!user) return null;

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
        <button
          type="button"
          onClick={() => window.location.assign('/')}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-med-primary hover:bg-med-primary-light transition-colors"
          title="Вернуться к регистратору"
        >
          <ArrowLeft className="h-4 w-4" />
          Регистратор
        </button>

        <div className="text-right">
          <div className="text-xs font-medium text-med-text-muted">{userRoleLabel(user)}</div>
          <div className="text-sm font-semibold text-med-text-primary">{user.name}</div>
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
          {userInitials(user.name)}
        </div>
      </div>
    </header>
  );
}
