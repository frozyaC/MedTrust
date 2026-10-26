import { useEffect, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { Check, Copy } from 'lucide-react';
import { copyText } from '../../lib/format';

interface CopyButtonProps {
  value: string;
  label?: string;
  className?: string;
  onCopied?: () => void;
}

export function CopyButton({ value, label, className, onCopied }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const handleClick = async (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    const success = await copyText(value);
    if (!success) return;

    setCopied(true);
    onCopied?.();
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title={copied ? 'Скопировано' : (label ?? 'Скопировать ID')}
      aria-label={copied ? 'Скопировано' : (label ?? 'Скопировать ID')}
      className={
        className ??
        'inline-flex items-center gap-1.5 rounded-md p-1 text-med-text-muted transition-colors hover:bg-med-bg hover:text-med-primary'
      }
    >
      {copied ? (
        <Check className="h-4 w-4 shrink-0 text-med-success" />
      ) : (
        <Copy className="h-4 w-4 shrink-0" />
      )}
      {label && <span>{copied ? 'Скопировано' : label}</span>}
    </button>
  );
}
