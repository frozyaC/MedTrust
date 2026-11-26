import { useState } from 'react';
import App from '../App';
import { KnowledgeGapsPage } from '../pages/KnowledgeGapsPage';
import { LoginPage } from '../components/LoginPage';
import { useAuth } from './AuthContext';

export function AuthenticatedApp() {
  const { user, loading, error, refresh, login, logout } = useAuth();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const currentPath = window.location.pathname.replace(/\/+$/, '');
  const isKnowledgeGapsPage = currentPath === '/admin/knowledge-gaps';

  if (loading) return <div className="flex min-h-screen items-center justify-center" role="status">Проверяем сессию…</div>;
  if (error) return <div className="flex min-h-screen flex-col items-center justify-center gap-4" role="alert">
    <p>{error}</p><button type="button" onClick={() => void refresh()}>Повторить</button>
  </div>;
  if (!user) return <LoginPage onLogin={login} />;
  if (isKnowledgeGapsPage && user.role !== 'kb_owner') return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#EFF6FF]">
      <h1 className="text-2xl font-semibold">Доступ запрещён</h1>
      <p>Карта пробелов доступна только руководителю.</p>
      <a className="text-blue-700 underline" href="/">Перейти в чат</a>
      <button type="button" onClick={() => { void logout().catch(() => setLogoutError('Не удалось выйти. Повторите попытку.')); }}>Выйти из аккаунта</button>
      {logoutError && <p role="alert">{logoutError}</p>}
    </div>
  );
  return isKnowledgeGapsPage ? <KnowledgeGapsPage key={user.id} /> : <App key={user.id} />;
}
