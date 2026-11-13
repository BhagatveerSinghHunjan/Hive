import type {
  AgentState,
  Budget,
  ChatMessage,
  ConnectionState,
  OverviewData,
  TimelineEvent,
} from '../types';
import type { Screen } from './Nav';
import { EventRow } from './EventRow';

interface DashboardProps {
  connected: ConnectionState;
  status: string;
  task: string;
  mode: string;
  elapsed: string;
  budget: Budget;
  agents: AgentState[];
  subtasks: { done: number; total: number };
  events: TimelineEvent[];
  messages: ChatMessage[];
  latestAssistant?: ChatMessage;
  processing: boolean;
  quickPrompts: string[];
  overview: OverviewData | null;
  pendingApprovals: number;
  onOpen: (screen: Screen) => void;
  onRefresh: () => void;
  onSubmit: (text: string) => void;
}

export function Dashboard({
  connected,
  status,
  task,
  mode,
  elapsed,
  budget,
  agents,
  subtasks,
  events,
  messages,
  latestAssistant,
  processing,
  quickPrompts,
  overview,
  pendingApprovals,
  onOpen,
  onRefresh,
  onSubmit,
}: DashboardProps) {
  const pct = Math.min(100, Math.round((budget.spent / Math.max(1, budget.total)) * 100));
  const activeAgents = agents.filter((a) => a.status === 'working' || a.status === 'spawning');
  const disabled = processing || connected !== 'connected';
  const recent = events.slice(-8).reverse();

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Task control</h1>
          <p>One queen, a temporary colony of specialists, and a single approval gate.</p>
        </div>
        <div className="page-head-status">
          <span className={`status-pill ${connected}`}>
            <span className="status-dot" />
            {connected === 'connected' ? 'Live' : connected === 'connecting' ? 'Starting' : 'Offline'}
          </span>
        </div>
      </div>

      <div className="dashboard-band">
        <section className="card span-4">
          <div className="card-label">Runtime</div>
          <div className="runtime-state">
            {connected === 'connected' ? 'Healthy' : connected === 'connecting' ? 'Booting…' : 'Exited'}
          </div>
          <div className="kv">
            <span>Status</span>
            <span>{status}</span>
          </div>
          <div className="kv">
            <span>Mode</span>
            <span>{mode}</span>
          </div>
          <div className="kv">
            <span>Elapsed</span>
            <span>{elapsed}</span>
          </div>
        </section>

        <section className="card span-5">
          <div className="card-label">Current task</div>
          <div className="mission-title">{task || 'No task yet — send one below.'}</div>
          <div className="progress-row">
            <span>
              Subtasks {subtasks.total > 0 ? `${subtasks.done} / ${subtasks.total}` : '—'}
            </span>
            <span>{processing ? 'agents working' : 'idle'}</span>
          </div>
          <div className="meter meter-lg">
            <div
              className="meter-fill"
              style={{
                width: `${subtasks.total > 0 ? Math.round((subtasks.done / subtasks.total) * 100) : 0}%`,
              }}
            />
          </div>
          {latestAssistant && (
            <div className="latest-response">
              <div className="card-label">Latest response</div>
              <p>{latestAssistant.content.slice(0, 900)}</p>
            </div>
          )}
        </section>

        <section className="card span-3">
          <div className="card-label">Credits</div>
          <div className="big-number">
            {budget.spent}
            <span className="big-number-sub"> / {budget.total}</span>
          </div>
          <div className="meter meter-lg">
            <div className="meter-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="card-foot">{budget.total - budget.spent} remaining</div>
        </section>
      </div>

      <section className="card">
        <div className="card-row">
          <div className="card-label">Club ops</div>
          <button type="button" className="ghost-btn btn-small" onClick={onRefresh}>
            Refresh
          </button>
        </div>
        {overview ? (
          <>
            <div className="ops-stats">
              <button className="ops-stat" onClick={() => onOpen('inbox')}>
                <span className="ops-stat-value">{overview.inbox.count}</span>
                <span className="ops-stat-label">Unread email</span>
              </button>
              <button className="ops-stat" onClick={() => onOpen('tasks')}>
                <span className="ops-stat-value">{overview.tasks.pending}</span>
                <span className="ops-stat-label">Pending tasks</span>
              </button>
              <button className="ops-stat" onClick={() => onOpen('calendar')}>
                <span className="ops-stat-value">{overview.agenda.count}</span>
                <span className="ops-stat-label">Events ahead</span>
              </button>
              <button className="ops-stat" onClick={() => onOpen('missions')}>
                <span className="ops-stat-value">{overview.missions}</span>
                <span className="ops-stat-label">To-dos</span>
              </button>
            </div>
            <div className="kv">
              <span>Next meeting</span>
              <span>
                {overview.agenda.next
                  ? `${overview.agenda.next.summary} · ${overview.agenda.next.start}`
                  : 'No events on the calendar'}
              </span>
            </div>
            <div className="connector-row">
              <span className={`connection-chip ${overview.connections.google_connected ? 'on' : ''}`}>
                <span className="status-dot" />
                Google {overview.connections.google_connected ? 'connected' : 'not connected'}
              </span>
              {overview.connections.google_email && (
                <span className="connection-email">{overview.connections.google_email}</span>
              )}
              <span className={`connection-chip ${overview.connections.slack_configured ? 'on' : ''}`}>
                <span className="status-dot" />
                Slack {overview.connections.slack_configured ? 'configured' : 'off'}
              </span>
              {overview.timezone && <span className="connection-email">{overview.timezone}</span>}
            </div>
            {(overview.inbox.needs_auth || overview.agenda.needs_auth) && (
              <div className="card-foot">
                Google needs authorization. Run <code>python -m hive.cli --connect-google</code>.
              </div>
            )}
          </>
        ) : (
          <div className="empty quiet">Waiting for the runtime snapshot.</div>
        )}
      </section>

      <div className="dashboard-band">
        <section className="card span-8">
          <div className="card-label">Active agents</div>
          {activeAgents.length === 0 ? (
            <div className="empty quiet">
              {agents.length > 0
                ? 'All agents finished. Check the execution monitor for the trail.'
                : 'No agents spawned yet. The leader routes each task.'}
            </div>
          ) : (
            <div className="agent-grid">
              {activeAgents.map((agent) => (
                <div key={agent.id} className="agent-chip">
                  <div className="agent-chip-head">
                    <span className="agent-dot" />
                    <span className="agent-kind">{agent.kind}</span>
                    <span className={`agent-status ${agent.status}`}>{agent.status}</span>
                  </div>
                  <div className="agent-task">{agent.task || agent.id}</div>
                </div>
              ))}
            </div>
          )}
          {agents.length > activeAgents.length && (
            <div className="card-foot">
              {agents.length - activeAgents.length} recent agent
              {agents.length - activeAgents.length === 1 ? '' : 's'} completed.
            </div>
          )}
        </section>

        <section className="card span-4">
          <div className="card-label">Approval gate</div>
          <div className="big-number">
            {pendingApprovals}
            <span className="big-number-sub"> waiting</span>
          </div>
          <p className="card-copy">
            Outbound email, calendar invites, and risky tool calls always stop for a human.
          </p>
          <button type="button" className="btn btn-approve" onClick={() => onOpen('approvals')}>
            Open approvals
          </button>
        </section>
      </div>

      <div className="dashboard-band">
        <section className="card span-6">
          <div className="card-label">Recent events</div>
          {recent.length === 0 ? (
            <div className="empty quiet">Events appear here as the society works.</div>
          ) : (
            <div className="event-list compact">
              {recent.map((event) => (
                <EventRow key={event.id} event={event} />
              ))}
            </div>
          )}
        </section>

        <section className="card span-6">
          <div className="card-label">Quick tasks</div>
          <div className="quick-list">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="quick-prompt"
                disabled={disabled}
                onClick={() => onSubmit(prompt)}
              >
                <span className="quick-arrow">→</span>
                {prompt}
              </button>
            ))}
          </div>
          <div className="card-foot">
            {messages.length > 0
              ? `${messages.length} messages in this session.`
              : 'Try a file task first — it exercises the approval gate.'}
          </div>
        </section>
      </div>
    </div>
  );
}
