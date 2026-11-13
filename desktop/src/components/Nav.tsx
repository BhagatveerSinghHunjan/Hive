import type { Budget, ConnectionState } from '../types';

export type Screen =
  | 'dashboard'
  | 'inbox'
  | 'calendar'
  | 'tasks'
  | 'missions'
  | 'monitor'
  | 'approvals';

interface NavProps {
  screen: Screen;
  setScreen: (screen: Screen) => void;
  pendingApprovals: number;
  inboxCount?: number;
  taskCount?: number;
  connected: ConnectionState;
  budget: Budget;
  onRestart: () => void;
}

const ITEMS: Array<{ id: Screen; label: string; icon: string; section: 'club' | 'system' }> = [
  { id: 'dashboard', label: 'Dashboard', icon: '◈', section: 'club' },
  { id: 'inbox', label: 'Inbox', icon: '✉', section: 'club' },
  { id: 'calendar', label: 'Calendar', icon: '▦', section: 'club' },
  { id: 'tasks', label: 'Tasks', icon: '☑', section: 'club' },
  { id: 'missions', label: 'Missions', icon: '✦', section: 'club' },
  { id: 'monitor', label: 'Execution Monitor', icon: '▤', section: 'system' },
  { id: 'approvals', label: 'Approvals', icon: '✓', section: 'system' },
];

export function Nav({
  screen,
  setScreen,
  pendingApprovals,
  inboxCount = 0,
  taskCount = 0,
  connected,
  budget,
  onRestart,
}: NavProps) {
  const pct = Math.min(100, Math.round((budget.spent / Math.max(1, budget.total)) * 100));

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">⬡</div>
        <div>
          <div className="brand-name">HIVE</div>
          <div className="brand-sub">DESKTOP</div>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-label">Club ops</div>
        {ITEMS.filter((item) => item.section === 'club').map((item) => {
          const badge =
            item.id === 'inbox' ? inboxCount : item.id === 'tasks' ? taskCount : 0;
          return (
            <button
              key={item.id}
              className={`nav-item ${screen === item.id ? 'active' : ''}`}
              onClick={() => setScreen(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-text">{item.label}</span>
              {badge > 0 && <span className="nav-badge">{badge}</span>}
            </button>
          );
        })}

        <div className="nav-label nav-label-spaced">System</div>
        {ITEMS.filter((item) => item.section === 'system').map((item) => (
          <button
            key={item.id}
            className={`nav-item ${screen === item.id ? 'active' : ''}`}
            onClick={() => setScreen(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-text">{item.label}</span>
            {item.id === 'approvals' && pendingApprovals > 0 && (
              <span className="nav-badge">{pendingApprovals}</span>
            )}
          </button>
        ))}

        <div className="nav-label nav-label-spaced">Post-demo</div>
        <button className="nav-item disabled" disabled title="Planned after the 60-minute demo">
          <span className="nav-icon">✦</span>
          <span className="nav-text">Agent Studio</span>
          <span className="nav-soon">soon</span>
        </button>
        <button className="nav-item disabled" disabled title="Planned after the 60-minute demo">
          <span className="nav-icon">▣</span>
          <span className="nav-text">Workspace</span>
          <span className="nav-soon">soon</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <div className={`sidebar-connection ${connected}`}>
          <span className="status-dot" />
          {connected === 'connected' ? 'Python runtime live' : connected === 'connecting' ? 'Starting runtime' : 'Runtime offline'}
        </div>

        <div className="budget">
          <div className="budget-row">
            <span>Session credits</span>
            <span className="budget-value">
              {budget.spent} / {budget.total}
            </span>
          </div>
          <div className="meter">
            <div className="meter-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <button className="sidebar-restart" onClick={onRestart}>
          ⟳ Restart runtime
        </button>

        <div className="sidebar-note">
          Electron shell · JSON-lines bridge
          <br />
          Qwen via HIVE leader
        </div>
      </div>
    </aside>
  );
}
