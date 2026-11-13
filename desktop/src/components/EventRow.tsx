import type { TimelineEvent } from '../types';

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function EventRow({ event }: { event: TimelineEvent }) {
  return (
    <div className={`event-row kind-${event.kind}`}>
      <span className="event-time">{formatTime(event.ts)}</span>
      <span className={`event-badge badge-${event.kind}`}>{event.kind}</span>
      <span className="event-body">
        <span className="event-title">{event.title}</span>
        {event.detail && <span className="event-detail">{event.detail}</span>}
      </span>
    </div>
  );
}
