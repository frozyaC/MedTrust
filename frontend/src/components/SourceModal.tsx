import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BookOpen, ExternalLink, Loader2, X } from 'lucide-react';
import { Source } from '../types';
import { fetchWikiContent } from '../api/knowledge';
import { QueryApiError } from '../api/query';
import { lockBodyScroll } from '../lib/scrollLock';

interface SourceModalProps {
  source: Source;
  onClose: () => void;
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; content: string }
  | { kind: 'fallback'; reason: string };

/**
 * Модалка «Открыть источник»: полный Markdown статьи из локальной БД.
 */
export const SourceModal: React.FC<SourceModalProps> = ({ source, onClose }) => {
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  useEffect(() => {
    return lockBodyScroll();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading' });

    const documentId = source.documentId;
    if (!documentId) {
      setState({
        kind: 'fallback',
        reason: 'Полный текст недоступен: у источника нет document_id.',
      });
      return () => {
        cancelled = true;
      };
    }

    fetchWikiContent(documentId)
      .then((data) => {
        if (cancelled) return;
        const content = (data.content ?? '').trim();
        if (!content) {
          setState({
            kind: 'fallback',
            reason: 'Сервер вернул пустой текст статьи.',
          });
          return;
        }
        setState({ kind: 'ready', content });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const detail =
          error instanceof QueryApiError ? error.message : 'Не удалось загрузить текст статьи';
        setState({ kind: 'fallback', reason: detail });
      });

    return () => {
      cancelled = true;
    };
  }, [source.documentId]);

  const pathLabel = source.path?.trim() || '';
  const sectionLabel = source.wikiDate?.trim() || '';
  const url = source.url?.trim() || '';

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 animate-fade-in bg-med-text-primary/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-modal-title"
        className="relative flex h-[85vh] w-full max-w-[860px] animate-slide-up flex-col overflow-hidden rounded-xl border border-med-border bg-med-surface shadow-med-panel"
      >
        <header className="flex items-start justify-between gap-3 border-b border-med-border px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-med-text-muted">
              <BookOpen className="h-4 w-4 text-med-primary" />
              Источник
            </div>
            <h2
              id="source-modal-title"
              className="mt-1 break-words text-lg font-semibold leading-6 text-med-text-primary"
            >
              {source.title}
            </h2>
            {(pathLabel || sectionLabel) && (
              <p className="mt-0.5 break-words text-xs text-med-text-secondary">
                {pathLabel}
                {pathLabel && sectionLabel ? ' › ' : ''}
                {sectionLabel}
              </p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-med-border bg-med-surface px-2.5 py-1.5 text-xs font-semibold text-med-primary transition-colors hover:bg-med-primary-light/40"
                title="Открыть в wiki.js"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Wiki.js
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-med-text-secondary transition-colors hover:bg-med-bg hover:text-med-text-primary"
              aria-label="Закрыть"
              title="Закрыть"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {state.kind === 'loading' && (
            <div className="flex items-center gap-2 text-sm text-med-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin text-med-primary" />
              Загружаем полный текст статьи…
            </div>
          )}

          {state.kind === 'fallback' && (
            <div className="space-y-3">
              <div className="rounded-lg border border-med-warning/40 bg-med-warning/10 px-3 py-2.5 text-xs leading-5 text-med-text-primary">
                {state.reason} Показан фрагмент, использованный в ответе.
              </div>
              <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-med-text-primary">
                {source.quote?.trim() || 'Фрагмент недоступен.'}
              </div>
            </div>
          )}

          {state.kind === 'ready' && (
            <div className="text-sm leading-relaxed text-med-text-primary answer-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  h1: ({ children }) => (
                    <h3 className="mt-4 mb-2 text-base font-semibold text-med-text-primary first:mt-0">
                      {children}
                    </h3>
                  ),
                  h2: ({ children }) => (
                    <h4 className="mt-3 mb-1.5 text-sm font-semibold text-med-text-primary">
                      {children}
                    </h4>
                  ),
                  h3: ({ children }) => (
                    <h5 className="mt-3 mb-1 text-sm font-semibold text-med-text-primary">
                      {children}
                    </h5>
                  ),
                  h4: ({ children }) => (
                    <h6 className="mt-2.5 mb-1 text-sm font-semibold text-med-text-primary">
                      {children}
                    </h6>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-med-text-primary">{children}</strong>
                  ),
                  em: ({ children }) => <em className="italic">{children}</em>,
                  ul: ({ children }) => (
                    <ul className="mb-2 ml-5 list-disc space-y-1 list-outside">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="mb-2 ml-5 list-decimal space-y-1 list-outside">{children}</ol>
                  ),
                  li: ({ children }) => <li className="pl-1">{children}</li>,
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-med-primary underline hover:text-med-primary-hover"
                    >
                      {children}
                    </a>
                  ),
                  code: ({ children }) => (
                    <code className="rounded bg-med-bg px-1 py-0.5 font-mono text-[12px]">
                      {children}
                    </code>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="my-2 border-l-2 border-med-primary/40 pl-3 italic text-med-text-secondary">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="my-2 overflow-x-auto">
                      <table className="w-full border-collapse text-xs">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-med-border bg-med-bg px-2 py-1 text-left font-semibold">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-med-border px-2 py-1">{children}</td>
                  ),
                  hr: () => <hr className="my-3 border-med-border" />,
                }}
              >
                {state.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-med-border bg-med-surface px-6 py-3">
          <span className="truncate text-xs text-med-text-muted">
            {source.path || 'Полный текст источника из локальной БД'}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-med-border bg-med-surface px-4 text-sm font-semibold text-med-text-secondary transition-colors hover:border-med-border-strong hover:bg-med-bg"
          >
            Закрыть
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
};