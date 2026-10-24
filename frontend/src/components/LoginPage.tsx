import React, { useState } from 'react';
import { LogIn, AlertCircle } from 'lucide-react';

interface LoginPageProps {
  onLogin: (login: string, password: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!login.trim() || !password.trim()) {
      setError('Введите логин и пароль');
      return;
    }

    setIsSubmitting(true);
    // Имитация задержки — чтобы было видно «Вход...» на кнопке
    window.setTimeout(() => {
      onLogin(login.trim(), password);
    }, 300);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#EFF6FF] px-4">
      <div className="w-full max-w-[400px] bg-white rounded-2xl border border-[#BFDBFE] shadow-lg p-8 space-y-6">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <img
            src="/medtrust.png"
            alt="MedTrust"
            className="w-16 h-16 object-contain"
          />
          <div className="text-center">
            <h1 className="font-bold text-2xl tracking-tight">
              <span className="text-[#243040]">Med</span>
              <span className="text-[#3076D7]">Trust</span>
            </h1>
            <p className="text-xs text-[#475569] mt-1">
              Интеллектуальный справочник регистратора
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label
              htmlFor="login"
              className="text-xs font-semibold text-[#0F172A]"
            >
              Логин
            </label>
            <input
              id="login"
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              placeholder="Введите логин"
              autoComplete="username"
              autoFocus
              className="w-full px-3 py-2.5 text-sm text-[#0F172A] bg-white border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
            />
          </div>

          <div className="space-y-1">
            <label
              htmlFor="password"
              className="text-xs font-semibold text-[#0F172A]"
            >
              Пароль
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Введите пароль"
              autoComplete="current-password"
              className="w-full px-3 py-2.5 text-sm text-[#0F172A] bg-white border border-[#BFDBFE] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#3B82F6] focus:border-transparent transition-all placeholder:text-[#94A3B8]"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 text-xs text-[#EF4444] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-semibold text-sm rounded-lg transition-colors shadow-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Вход...</span>
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Войти</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};