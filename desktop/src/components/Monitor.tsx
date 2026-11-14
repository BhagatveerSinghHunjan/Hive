import { useEffect, useRef, useState } from 'react';
import type { AgentState, TimelineEvent, ToolCall } from '../types';
import { EventRow } from './EventRow';
import { EmptyState, PageShell } from './PageShell';

interface MonitorProps {
  events: TimelineEvent[];
  agents: AgentState[];
  toolCalls: ToolCall[];
  streamText: string;
  processing: boolean;
  logs: string[];
  onOpenChat?: () => void;
}

function toolSummary(call: ToolCall): string {
  const args = call.args || {};
  const bits: string[] = [call.tool];
  for (const key of ['to', 'summary', 'location', 'query', 'path', 'subject', 'title']) {
    const value = args[key];
    if (value != null && String(value).trim()) {
      bits.push(String(value).slice(0, 48));
      break;
    }
  }
  if (args.reminders_minutes != null) bits.push(`reminders ${args.reminders_minutes}m`);
  if (args.start && args.end) bits.push(`${String(args.start).slice(0, 16)} → ${String(args.end).slice(0, 16)}`);
  return bits.join(' · ');
}

export function Monitor({
  events,
  agents,
  toolCalls,
  streamText,
  processing,
  logs,
  onOpenChat,
}: MonitorProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length, streamText]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs.length, showLogs]);

  const idleEmpty = !processing && !streamText && toolCalls.length === 0 && events.length === 0;

  return (
    <PageShell
      className="monitor"
      compact
      title="Activity"
      purpose="See what HIVE is saying and which steps it took. Approvals still land on the Approvals page."
      meta={
        <div className="monitor-live">
          <span className={`live-dot ${processing ? 'busy' : ''}`} />
          {processing ? 'Working' : 'Listening'}
        </div>
      }
    >
      {idleEmpty ? (
        <EmptyState
          icon="▤"
          title="No activity yet"
          body="Send a task from Chat to watch live replies and tool steps here."
          actionLabel="Open Chat"
          onAction={onOpenChat}
        />
      ) : (
        <div className="activity-stack">
          <div className="activity-primary">
            <section className={`stream-box ${streamText ? 'has-text' : ''}`}>
              <div className="stream-head">
                <span>What HIVE is saying</span>
                <span className="stream-count">
                  {streamText ? `${streamText.length.toLocaleString()} chars` : processing ? '…' : 'idle'}
                </span>
              </div>
              <div className="stream-text">
                {streamText ||
                  (processing ? 'Waiting for the first token…' : 'No live output for this moment.')}
                {processing && <span className="cursor">▋</span>}
              </div>
            </section>

            <section className="rail-card">
              <div className="card-label">What HIVE did</div>
              {toolCalls.length === 0 ? (
                <div className="empty quiet small">No tool steps yet.</div>
              ) : (
                <div className="rail-list">
                  {toolCalls
                    .slice()
                    .reverse()
                    .map((call) => (
                      <div key={call.id} className="tool-step">
                        <div className="tool-step-summary">{toolSummary(call)}</div>
                        <div className="tool-step-time">
                          {new Date(call.ts).toLocaleTimeString([], { hour12: false })}
                        </div>
                        <details>
                          <summary>Details</summary>
                          <pre className="args">{JSON.stringify(call.args, null, 2).slice(0, 800)}</pre>
                        </details>
                      </div>
                    ))}
                </div>
              )}
            </section>
          </div>

          <div className="activity-secondary">
            <section className="timeline panel" ref={scrollRef}>
              <div className="panel-head">
                <span className="card-label">Timeline</span>
                <span className="panel-meta">{events.length} events</span>
              </div>
              <div className="panel-body">
                {events.length === 0 ? (
                  <div className="empty quiet">Events appear as HIVE works.</div>
                ) : (
                  events.map((event) => <EventRow key={event.id} event={event} />)
                )}
              </div>
            </section>

            <aside className="rail">
              {agents.length > 0 && (
                <section className="rail-card">
                  <div className="card-label">Agents</div>
                  <div className="rail-list">
                    {agents.map((agent) => (
                      <div key={agent.id} className="rail-item">
                        <div className="rail-item-head">
                          <span className="agent-kind">{agent.kind}</span>
                          <span className={`agent-status ${agent.status}`}>{agent.status}</span>
                        </div>
                        <div className="rail-item-sub">{agent.task || agent.id}</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="rail-card rail-logs">
                <div className="panel-head">
                  <span className="card-label">Runtime log</span>
                  <button
                    type="button"
                    className="ghost-btn btn-small"
                    onClick={() => setShowLogs((v) => !v)}
                  >
                    {showLogs ? 'Hide' : 'Show'}
                  </button>
                </div>
                {showLogs &&
                  (logs.length === 0 ? (
                    <div className="empty quiet">No runtime output yet.</div>
                  ) : (
                    <div className="log-lines" ref={logRef}>
                      {logs.slice(-40).map((line, index) => (
                        <div key={`${index}-${line.slice(0, 20)}`} className="log-line">
                          {line}
                        </div>
                      ))}
                    </div>
                  ))}
                {!showLogs && (
                  <div className="empty quiet small">{logs.length} lines hidden — for debugging only.</div>
                )}
              </section>
            </aside>
          </div>
        </div>
      )}
    </PageShell>
  );
}
