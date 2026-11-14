import type {
  ChatMessage,
  ConnectionState,
  OverviewData,
} from '../types';
import type { Screen } from './Nav';
import { EmptyState, PageShell } from './PageShell';

interface DashboardProps {
  connected: ConnectionState;
  status: string;
  task: string;
  mode: string;
  elapsed: string;
  budget: { spent: number; total: number };
  agents: unknown[];
  subtasks: { done: number; total: number };
  events: unknown[];
  messages: ChatMessage[];
  latestAssistant?: ChatMessage;
  processing: boolean;
  quickPrompts: string[];
  overview: OverviewData | null;
  pendingApprovals: number;
  spotifyConnected?: boolean;
  onOpen: (screen: Screen) => void;
  onRefresh: () => void;
  onSubmit: (text: string) => void;
}

export function Dashboard({
  connected,
  processing,
  quickPrompts,
  overview,
  pendingApprovals,
  latestAssistant,
  spotifyConnected = false,
  onOpen,
  onRefresh,
  onSubmit,
}: DashboardProps) {
  const disabled = processing || connected !== 'connected';
  const googleOk = overview?.connections.google_connected;
  const needsAuth = Boolean(overview?.inbox.needs_auth || overview?.agenda.needs_auth);
  const nextMeeting = overview?.agenda.next;

  return (
    <PageShell
      className="dashboard"
      title="Home"
      purpose="Today’s club snapshot — inbox, agenda, tasks, and anything waiting for your approval."
      meta={
        <span className={`status-pill ${connected}`}>
          <span className="status-dot" />
          {connected === 'connected' ? 'Live' : connected === 'connecting' ? 'Starting' : 'Offline'}
        </span>
      }
      action={
        <button type="button" className="ghost-btn btn-small" onClick={onRefresh}>
          Refresh
        </button>
      }
    >
      <div className="home-stack">
        {overview ? (
          <div className="home-stats">
            <button type="button" className="home-stat" onClick={() => onOpen('inbox')}>
              <span className="home-stat-value">{overview.inbox.count}</span>
              <span className="home-stat-label">Unread email</span>
              <span className="home-stat-hint">Open Inbox</span>
            </button>
            <button type="button" className="home-stat" onClick={() => onOpen('calendar')}>
              <span className="home-stat-value">{overview.agenda.count}</span>
              <span className="home-stat-label">Events ahead</span>
              <span className="home-stat-hint">
                {nextMeeting ? nextMeeting.summary : 'Calendar clear'}
              </span>
            </button>
            <button type="button" className="home-stat" onClick={() => onOpen('tasks')}>
              <span className="home-stat-value">{overview.tasks.pending}</span>
              <span className="home-stat-label">Tasks due</span>
              <span className="home-stat-hint">Open Tasks</span>
            </button>
            <button type="button" className="home-stat" onClick={() => onOpen('approvals')}>
              <span className="home-stat-value">{pendingApprovals}</span>
              <span className="home-stat-label">Approvals waiting</span>
              <span className="home-stat-hint">
                {pendingApprovals > 0 ? 'Needs your decision' : 'All clear'}
              </span>
            </button>
          </div>
        ) : (
          <EmptyState
            icon="◈"
            title="Waiting for snapshot"
            body="Home loads inbox, agenda, and tasks once the runtime is connected."
            actionLabel="Refresh"
            onAction={onRefresh}
          />
        )}

        <div className="home-band">
          <section className="card home-panel">
            <div className="card-label">Connections</div>
            <div className="connector-row">
              <span className={`connection-chip ${googleOk ? 'on' : ''}`}>
                <span className="status-dot" />
                Google {googleOk ? 'connected' : 'not connected'}
              </span>
              <span className={`connection-chip ${spotifyConnected ? 'on' : ''}`}>
                <span className="status-dot" />
                Spotify {spotifyConnected ? 'connected' : 'not connected'}
              </span>
              {overview?.connections.google_email && (
                <span className="connection-email">{overview.connections.google_email}</span>
              )}
              {overview?.timezone && <span className="connection-email">{overview.timezone}</span>}
            </div>
            {needsAuth && (
              <div className="card-foot">
                Connect Google in Settings to unlock Inbox and Calendar.
              </div>
            )}
            <div className="card-actions">
              <button type="button" className="btn" onClick={() => onOpen('settings')}>
                {needsAuth || !spotifyConnected ? 'Open Settings' : 'Manage connections'}
              </button>
              <button
                type="button"
                className="ghost-btn"
                disabled={disabled}
                onClick={() => onSubmit(quickPrompts[3] ?? 'Give me my morning brief.')}
              >
                Morning brief
              </button>
            </div>
          </section>

          <section className="card home-panel">
            <div className="card-label">Latest from HIVE</div>
            {latestAssistant ? (
              <p className="card-copy">{latestAssistant.content.slice(0, 420)}</p>
            ) : (
              <p className="card-copy">No replies yet. Ask something in Chat or run a workflow.</p>
            )}
            <div className="card-actions">
              <button type="button" className="ghost-btn btn-small" onClick={() => onOpen('chat')}>
                Open Chat
              </button>
            </div>
          </section>
        </div>

        <section className="card home-panel">
          <div className="card-label">Quick starts</div>
          <div className="quick-list">
            {quickPrompts.slice(0, 3).map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="quick-prompt"
                disabled={disabled}
                onClick={() => onSubmit(prompt)}
              >
                <span className="quick-arrow" aria-hidden>
                  →
                </span>
                <span className="quick-prompt-text">{prompt}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </PageShell>
  );
}
