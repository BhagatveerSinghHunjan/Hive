import type { Budget, ConnectionState } from '../types';

export type Screen = 'dashboard' | 'monitor' | 'approvals';

interface NavProps {
  screen: Screen;
  setScreen: (screen: Screen) => void;
  pendingApprovals: number;
  connected: ConnectionState;
  budget: Budget;
  onRestart: () => void;
}

const ITEMS: Array<{ id: Screen; label: string; icon: string }> = [
  { id: 'dashboard', label: 'Dashboard', icon: '◈' },
  { id: 'monitor', label: 'Execution Monitor', icon: '▤' },
  { id: 'approvals', label: 'Approvals', icon: '✓' },
];

export function Nav({ screen, setScreen, pendingApprovals, connected, budget, onRestart }: NavProps) {
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
        <div className="nav-label">Workspace</div>
        {ITEMS.map((item) => (
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
