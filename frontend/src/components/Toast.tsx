import React, { useEffect } from 'react';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';

interface ToastProps {
  message: string;
  type?: 'success' | 'info' | 'warning';
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type = 'success', onClose }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-[#0F172A] text-white px-4 py-3 rounded-xl shadow-lg border border-slate-700 animate-slide-up max-w-md">
      {type === 'success' ? (
        <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0" />
      ) : (
        <AlertCircle className="w-5 h-5 text-[#3B82F6] shrink-0" />
      )}
      <span className="text-xs font-medium leading-normal">{message}</span>
      <button
        onClick={onClose}
        className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors ml-auto"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
