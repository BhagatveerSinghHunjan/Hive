import type { ConnectionState } from '../types';

interface HeaderProps {
  connected: ConnectionState;
  status: string;
  task: string;
  elapsed: string;
  processing: boolean;
  onRestart: () => void;
}

/**
 * Only shows while a run is active or the runtime is down.
 * Idle pages keep a clean top edge — no Live/auto/last-message strip.
 */
export function Header({
  connected,
  status,
  task,
  elapsed,
  processing,
  onRestart,
}: HeaderProps) {
  if (connected === 'connected' && !processing) {
    return null;
  }

  const offline = connected !== 'connected';
  const label = offline
    ? connected === 'connecting'
      ? 'Starting runtime…'
      : 'Runtime offline'
    : status === 'routing'
      ? 'Planning…'
      : status.startsWith('running')
        ? status
        : 'Working…';

  return (
    <header className={`header header-run ${offline ? 'is-offline' : ''}`}>
      <div className="header-left">
        <span className={`status-pill ${connected}`}>
          <span className="status-dot" />
          {offline ? (connected === 'connecting' ? 'Starting' : 'Offline') : 'Working'}
        </span>
      </div>

      <div className="header-center">
        <div className="header-task" title={task}>
          {offline ? label : task || label}
        </div>
        {processing && (
          <div className="header-meta">
            <span>{elapsed}</span>
          </div>
        )}
      </div>

      <div className="header-right">
        <button type="button" className="ghost-btn" onClick={onRestart} title="Restart runtime">
          Restart
        </button>
      </div>
    </header>
  );
}
