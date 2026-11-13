import type {
  AgentState,
  Budget,
  ChatMessage,
  ConnectionState,
  TimelineEvent,
} from '../types';
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
          <h1>Mission control</h1>
          <p>One runtime, a society of agents, and a single approval gate.</p>
        </div>
        <div className="page-head-status">
          <span className={`status-pill ${connected}`}>
            <span className="status-dot" />
            {connected === 'connected' ? 'Live' : connected === 'connecting' ? 'Starting' : 'Offline'}
          </span>
        </div>
      </div>

      <div className="grid">
        <section className="card span-4">
          <div className="card-label">Runtime</div>
          <div className="runtime-state">{connected === 'connected' ? 'Healthy' : connected === 'connecting' ? 'Booting…' : 'Exited'}</div>
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
          <div className="card-foot">Electron main ↔ JSON-lines ↔ <code>hive.cli --server</code></div>
        </section>

        <section className="card span-8">
          <div className="card-label">Current mission</div>
          <div className="mission-title">{task || 'No mission yet — send a task below.'}</div>
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

        <section className="card span-4">
          <div className="card-label">Credits</div>
          <div className="big-number">
            {budget.spent}
            <span className="big-number-sub"> / {budget.total}</span>
          </div>
          <div className="meter meter-lg">
            <div className="meter-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="card-foot">
            {budget.total - budget.spent} credits remaining · tracked from spend/earn events
          </div>
        </section>

        <section className="card span-8">
          <div className="card-label">Active agents</div>
          {activeAgents.length === 0 ? (
            <div className="empty small">
              {agents.length > 0 ? 'All agents finished. Check the execution monitor for the trail.' : 'No agents spawned yet. The leader routes each task.'}
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
              {agents.length - activeAgents.length} recent agent{agents.length - activeAgents.length === 1 ? '' : 's'} completed.
            </div>
          )}
        </section>

        <section className="card span-6">
          <div className="card-label">Recent events</div>
          {recent.length === 0 ? (
            <div className="empty small">Events appear here as the society works.</div>
          ) : (
            <div className="event-list compact">
              {recent.map((event) => (
                <EventRow key={event.id} event={event} />
              ))}
            </div>
          )}
        </section>

        <section className="card span-6">
          <div className="card-label">Quick missions</div>
          <div className="quick-list">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
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
