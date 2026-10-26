import { useEffect, useRef } from 'react';
import type { FC } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, X, XCircle } from 'lucide-react';

export type ToastType = 'success' | 'info' | 'warning' | 'error';

interface ToastProps {
  message: string;
  type?: ToastType;
  onClose: () => void;
  actionLabel?: string;
  onAction?: () => void;
  duration?: number;
}

export const Toast: FC<ToastProps> = ({
  message,
  type = 'success',
  onClose,
  actionLabel,
  onAction,
  duration,
}) => {
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const timeout = duration ?? (type === 'error' || actionLabel ? 8000 : 4000);
    const timer = window.setTimeout(() => {
      onCloseRef.current();
    }, timeout);
    return () => window.clearTimeout(timer);
  }, [actionLabel, duration, message, type]);

  const isError = type === 'error';
  const isWarning = type === 'warning';

  return (
    <div
      role={isError ? 'alert' : 'status'}
      className={`fixed bottom-6 right-6 z-[80] flex max-w-md animate-slide-up items-center gap-3 rounded-xl border px-4 py-3 text-white shadow-lg ${
        isError ? 'border-med-error bg-med-error' : 'border-med-text-primary bg-med-text-primary'
      }`}
    >
      {isError ? (
        <XCircle className="h-5 w-5 shrink-0 text-white" />
      ) : isWarning ? (
        <AlertTriangle className="h-5 w-5 shrink-0 text-med-warning" />
      ) : type === 'info' ? (
        <AlertCircle className="h-5 w-5 shrink-0 text-med-accent" />
      ) : (
        <CheckCircle2 className="h-5 w-5 shrink-0 text-med-success" />
      )}

      <span className="text-xs font-medium leading-normal">{message}</span>

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={() => {
            onClose();
            onAction();
          }}
          className="ml-2 shrink-0 rounded-md bg-white/10 px-2 py-1 text-xs font-semibold text-white transition-colors hover:bg-white/20"
        >
          {actionLabel}
        </button>
      )}

      <button
        type="button"
        onClick={onClose}
        className="ml-auto rounded-lg p-1 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        aria-label="Закрыть уведомление"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};