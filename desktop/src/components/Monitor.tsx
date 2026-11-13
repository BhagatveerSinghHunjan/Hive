import { useEffect, useRef } from 'react';
import type { AgentState, TimelineEvent, ToolCall } from '../types';
import { EventRow } from './EventRow';

interface MonitorProps {
  events: TimelineEvent[];
  agents: AgentState[];
  toolCalls: ToolCall[];
  streamText: string;
  processing: boolean;
  logs: string[];
}

export function Monitor({ events, agents, toolCalls, streamText, processing, logs }: MonitorProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length, streamText]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs.length]);

  return (
    <div className="monitor">
      <div className="page-head compact-head">
        <div>
          <h1>Execution monitor</h1>
          <p>Every tool call, agent transition, and approval request in one trail.</p>
        </div>
        <div className="monitor-live">
          <span className={`live-dot ${processing ? 'busy' : ''}`} />
          {processing ? 'run in progress' : 'listening'}
        </div>
      </div>

      <section className={`stream-box ${streamText ? 'has-text' : ''}`}>
        <div className="stream-head">
          <span>Live output</span>
          <span className="stream-count">{streamText.length.toLocaleString()} chars</span>
        </div>
        <div className="stream-text">
          {streamText ||
            (processing ? 'Waiting for the first token…' : 'No active stream. Send a task to start.')}
          {processing && <span className="cursor">▋</span>}
        </div>
      </section>

      <section className="timeline panel" ref={scrollRef}>
        <div className="panel-head">
          <span className="card-label">Timeline</span>
          <span className="panel-meta">{events.length} events</span>
        </div>
        <div className="panel-body">
          {events.length === 0 ? (
            <div className="empty quiet">
              The timeline is empty. Send a task from the composer to watch the hive work.
            </div>
          ) : (
            events.map((event) => <EventRow key={event.id} event={event} />)
          )}
        </div>
      </section>

      <aside className="rail">
        <section className="rail-card">
          <div className="card-label">Agents</div>
          {agents.length === 0 ? (
            <div className="empty quiet">No agents in this run.</div>
          ) : (
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
          )}
        </section>

        <section className="rail-card">
          <div className="card-label">Tool calls</div>
          {toolCalls.length === 0 ? (
            <div className="empty quiet">No tool calls yet.</div>
          ) : (
            <div className="rail-list">
              {toolCalls
                .slice()
                .reverse()
                .map((call) => (
                  <div key={call.id} className="rail-item">
                    <div className="rail-item-head">
                      <span className="tool-name">{call.tool}</span>
                      <span className="rail-time">
                        {new Date(call.ts).toLocaleTimeString([], { hour12: false })}
                      </span>
                    </div>
                    <pre className="args">{JSON.stringify(call.args, null, 2).slice(0, 500)}</pre>
                  </div>
                ))}
            </div>
          )}
        </section>

        <section className="rail-card rail-logs">
          <div className="panel-head">
            <span className="card-label">Runtime log</span>
            <span className="panel-meta">{logs.length} lines</span>
          </div>
          {logs.length === 0 ? (
            <div className="empty quiet">No runtime output yet.</div>
          ) : (
            <div className="log-lines" ref={logRef}>
              {logs.slice(-40).map((line, index) => (
                <div key={`${index}-${line.slice(0, 20)}`} className="log-line">
                  {line}
                </div>
              ))}
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}
