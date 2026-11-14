import { useRef, useState } from 'react';
import type { Budget, ConnectionState } from '../types';

export type Screen =
  | 'chat'
  | 'dashboard'
  | 'inbox'
  | 'calendar'
  | 'tasks'
  | 'missions'
  | 'monitor'
  | 'approvals'
  | 'settings';

interface NavProps {
  screen: Screen;
  setScreen: (screen: Screen) => void;
  pendingApprovals: number;
  inboxCount?: number;
  taskCount?: number;
  connected: ConnectionState;
  budget: Budget;
  onRestart: () => void;
  onEgg?: (message: string) => void;
}

const ITEMS: Array<{ id: Screen; label: string; icon: string }> = [
  { id: 'chat', label: 'Chat', icon: '◎' },
  { id: 'dashboard', label: 'Home', icon: '◈' },
  { id: 'inbox', label: 'Inbox', icon: '✉' },
  { id: 'calendar', label: 'Calendar', icon: '▦' },
  { id: 'tasks', label: 'Tasks', icon: '☑' },
  { id: 'missions', label: 'Workflows', icon: '✦' },
  { id: 'approvals', label: 'Approvals', icon: '✓' },
  { id: 'monitor', label: 'Activity', icon: '▤' },
  { id: 'settings', label: 'Connections', icon: '⚙' },
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
  onEgg,
}: NavProps) {
  const pct = Math.min(100, Math.round((budget.spent / Math.max(1, budget.total)) * 100));
  const taps = useRef(0);
  const resetTimer = useRef<number | null>(null);
  const [buzzing, setBuzzing] = useState(false);

  const tapBrand = () => {
    taps.current += 1;
    if (resetTimer.current !== null) window.clearTimeout(resetTimer.current);
    resetTimer.current = window.setTimeout(() => {
      taps.current = 0;
    }, 1600);
    if (taps.current < 5) return;
    taps.current = 0;
    setBuzzing(true);
    window.setTimeout(() => setBuzzing(false), 700);
    onEgg?.('Club ops is online.');
  };

  const badgeFor = (id: Screen) => {
    if (id === 'inbox') return inboxCount;
    if (id === 'tasks') return taskCount;
    if (id === 'approvals') return pendingApprovals;
    return 0;
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <button
          type="button"
          className="brand brand-hit"
          onClick={tapBrand}
          title="HIVE — club operations"
        >
          <div className={`brand-mark ${buzzing ? 'buzz' : ''}`} aria-hidden>
            <img className="brand-logo" src="./logo.svg" alt="HIVE" />
          </div>
          <div className="brand-copy">
            <div className="brand-name">HIVE</div>
            <div className="brand-sub">Club ops</div>
          </div>
        </button>

        <nav className="nav" aria-label="Primary">
          {ITEMS.map((item) => {
            const badge = badgeFor(item.id);
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${screen === item.id ? 'active' : ''}`}
                onClick={() => setScreen(item.id)}
              >
                <span className="nav-icon" aria-hidden>
                  {item.icon}
                </span>
                <span className="nav-text">{item.label}</span>
                {badge > 0 && <span className="nav-badge">{badge}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className={`sidebar-connection ${connected}`}>
          <span className="status-dot" />
          <span>
            {connected === 'connected'
              ? 'Runtime live'
              : connected === 'connecting'
                ? 'Starting…'
                : 'Runtime offline'}
          </span>
        </div>

        <div className="budget-card" title="Session tool spend">
          <div className="budget-row">
            <span>Session spend</span>
            <span className="budget-value">
              {budget.spent} / {budget.total}
            </span>
          </div>
          <div className="meter">
            <div className="meter-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <button type="button" className="sidebar-restart" onClick={onRestart}>
          Restart runtime
        </button>
      </div>
    </aside>
  );
}
