import type { ConnectionState } from '../types';

interface HeaderProps {
  connected: ConnectionState;
  status: string;
  task: string;
  elapsed: string;
  mode: string;
  onRestart: () => void;
}

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: 'Starting',
  connected: 'Live',
  exited: 'Offline',
};

export function Header({ connected, status, task, elapsed, mode, onRestart }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <span className={`status-pill ${connected}`}>
          <span className="status-dot" />
          {CONNECTION_LABEL[connected]}
        </span>
        <span className="header-mode">{mode}</span>
      </div>

      <div className="header-center">
        <div className="header-task" title={task}>
          {task || 'No active task'}
        </div>
        <div className="header-meta">
          <span>{status}</span>
          <span className="sep">·</span>
          <span>{elapsed}</span>
        </div>
      </div>

      <div className="header-right">
        <button type="button" className="ghost-btn" onClick={onRestart} title="Restart runtime">
          Restart
        </button>
      </div>
    </header>
  );
}
