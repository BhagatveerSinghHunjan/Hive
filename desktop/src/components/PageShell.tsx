import type { ReactNode } from 'react';

interface PageShellProps {
  title: string;
  purpose: string;
  meta?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  compact?: boolean;
}

export function PageShell({
  title,
  purpose,
  meta,
  action,
  children,
  className = '',
  compact = false,
}: PageShellProps) {
  return (
    <div className={`page-shell ${compact ? 'page-shell-compact' : ''} ${className}`.trim()}>
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          <p>{purpose}</p>
        </div>
        {(meta || action) && (
          <div className="page-head-actions">
            {meta}
            {action}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

interface EmptyStateProps {
  icon?: string;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
}

export function EmptyState({
  icon = '⬡',
  title,
  body,
  actionLabel,
  onAction,
  actionDisabled,
}: EmptyStateProps) {
  return (
    <div className="empty empty-directed">
      <div className="empty-icon" aria-hidden>
        {icon}
      </div>
      <h2>{title}</h2>
      <p>{body}</p>
      {actionLabel && onAction && (
        <button type="button" className="btn" onClick={onAction} disabled={actionDisabled}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
