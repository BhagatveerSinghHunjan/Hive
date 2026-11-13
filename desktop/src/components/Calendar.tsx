import { useCallback, useEffect, useState } from 'react';
import type { AgendaEvent, RequestFn } from '../types';

interface CalendarProps {
  request: RequestFn;
  refreshKey: number;
  onAsk: (text: string) => void;
}

function parseDate(value?: string): Date | null {
  if (!value) return null;
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dayLabel(value?: string): string {
  const date = parseDate(value);
  if (!date) return 'Unscheduled';
  return date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

function timeLabel(event: AgendaEvent): string {
  if (event.start?.length === 10) return 'All day';
  const start = parseDate(event.start);
  if (!start) return '';
  const startText = start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const end = parseDate(event.end);
  if (!end) return startText;
  return `${startText} – ${end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

export function CalendarScreen({ request, refreshKey, onAsk }: CalendarProps) {
  const [events, setEvents] = useState<AgendaEvent[]>([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [needsAuth, setNeedsAuth] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('agenda', { days });
      setEvents(data.events ?? []);
      setNeedsAuth(Boolean(data.needs_auth));
      if (!data.ok) setError(String(data.error ?? 'Calendar unavailable'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [days, request]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const grouped = events.reduce<Array<{ label: string; events: AgendaEvent[] }>>((groups, event) => {
    const label = dayLabel(event.start);
    const existing = groups.find((group) => group.label === label);
    if (existing) existing.events.push(event);
    else groups.push({ label, events: [event] });
    return groups;
  }, []);

  return (
    <div className="ops-page">
      <div className="page-head">
        <div>
          <h1>Calendar</h1>
          <p>Your agenda, pulled live from Google Calendar. Meeting prep uses these events.</p>
        </div>
        <div className="page-head-actions">
          <div className="segmented">
            {[1, 7, 14].map((option) => (
              <button
                key={option}
                className={`segment ${days === option ? 'active' : ''}`}
                onClick={() => setDays(option)}
              >
                {option}d
              </button>
            ))}
          </div>
          <button type="button" className="ghost-btn btn-small" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {needsAuth && (
        <div className="banner banner-warn">
          <div>
            <strong>Google Calendar is not authorized.</strong> Run{' '}
            <code>python -m hive.cli --connect-google</code>, then refresh.
          </div>
        </div>
      )}

      {error && !needsAuth && <div className="banner banner-error">{error}</div>}

      {grouped.length === 0 && !loading ? (
        <div className="empty">
          <div className="empty-icon">▦</div>
          <h2>No events ahead</h2>
          <p>The next {days} day{days === 1 ? '' : 's'} are clear. Ask HIVE to schedule something.</p>
        </div>
      ) : (
        <div className="agenda">
          {grouped.map((group) => (
            <section key={group.label} className="agenda-day">
              <div className="agenda-day-label">{group.label}</div>
              <div className="agenda-events">
                {group.events.map((event, index) => (
                  <article key={event.event_id ?? `${group.label}-${index}`} className="event-card">
                    <div className="event-time-chip">{timeLabel(event)}</div>
                    <div className="event-main">
                      <h3>{event.summary}</h3>
                      {event.location && <div className="event-meta">📍 {event.location}</div>}
                      {event.attendees && event.attendees.length > 0 && (
                        <div className="event-meta">
                          {event.attendees.length} attendee{event.attendees.length === 1 ? '' : 's'}
                          {event.attendees[0]?.email ? ` · ${event.attendees[0].email}` : ''}
                        </div>
                      )}
                      {event.description && (
                        <p className="event-description">{event.description.slice(0, 240)}</p>
                      )}
                    </div>
                    <div className="event-actions">
                      {event.meet_link && (
                        <a className="btn btn-small" href={event.meet_link} target="_blank" rel="noreferrer">
                          Join
                        </a>
                      )}
                      {event.html_link && (
                        <a className="btn btn-small" href={event.html_link} target="_blank" rel="noreferrer">
                          Open
                        </a>
                      )}
                      <button
                        className="btn btn-small btn-approve"
                        onClick={() =>
                          onAsk(`Prepare me for the meeting “${event.summary}” on ${event.start}.`)
                        }
                      >
                        Prep me
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
