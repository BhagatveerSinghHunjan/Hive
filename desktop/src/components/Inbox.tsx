import { useCallback, useEffect, useState } from 'react';
import type { InboxItem, RequestFn } from '../types';

interface InboxProps {
  request: RequestFn;
  refreshKey: number;
  onNotify: (kind: string, title: string, detail?: string) => void;
}

export function InboxScreen({ request, refreshKey, onNotify }: InboxProps) {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [needsAuth, setNeedsAuth] = useState(false);
  const [drafting, setDrafting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('inbox', { limit: 20 });
      setItems(data.items ?? []);
      setNeedsAuth(Boolean(data.needs_auth));
      if (!data.ok) setError(String(data.error ?? 'Inbox unavailable'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const draftReply = useCallback(
    async (item: InboxItem) => {
      if (!item.thread_id) return;
      setDrafting(item.thread_id);
      setError('');
      try {
        const data = await request('draft_reply', {
          thread_id: item.thread_id,
          subject: item.subject,
        });
        if (data.ok) {
          onNotify('response', 'Draft created', `Draft for “${item.subject}” is waiting in Gmail.`);
        } else {
          setError(String(data.error ?? 'Could not create draft'));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setDrafting(null);
      }
    },
    [onNotify, request]
  );

  const unread = items.filter((item) => item.unread).length;

  return (
    <div className="ops-page">
      <div className="page-head">
        <div>
          <h1>Inbox</h1>
          <p>Unread mail, classified by urgency. Drafts are prepared for review — never auto-sent.</p>
        </div>
        <div className="page-head-actions">
          <span className="pending-pill">{unread} unread</span>
          <button className="ghost-btn" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {needsAuth && (
        <div className="banner banner-warn">
          <div>
            <strong>Gmail is not authorized.</strong> Run{' '}
            <code>python -m hive.cli --connect-google</code>, then refresh.
          </div>
        </div>
      )}

      {error && !needsAuth && <div className="banner banner-error">{error}</div>}

      <div className="item-list">
        {items.length === 0 && !loading ? (
          <div className="empty">
            <div className="empty-icon">✉</div>
            <h2>Inbox zero</h2>
            <p>No unread messages in the last 14 days. New mail appears here after a refresh.</p>
          </div>
        ) : (
          items.map((item, index) => (
            <article
              key={item.message_id ?? `${item.thread_id}-${index}`}
              className={`mail-item priority-${item.priority}`}
            >
              <div className="mail-main">
                <div className="mail-meta">
                  <span className={`priority-badge priority-${item.priority}`}>{item.priority}</span>
                  <span className="mail-from">{item.from || 'unknown sender'}</span>
                  {item.date && <span className="mail-date">{item.date}</span>}
                  {item.unread && <span className="unread-dot" />}
                </div>
                <h3 className="mail-subject">{item.subject}</h3>
                {item.snippet && <p className="mail-snippet">{item.snippet}</p>}
                <div className="tag-row">
                  {(item.categories ?? []).map((category) => (
                    <span key={category} className="tag">
                      {category}
                    </span>
                  ))}
                  {item.needs_reply && <span className="tag tag-action">needs reply</span>}
                </div>
              </div>
              <button
                className="btn btn-approve btn-small"
                disabled={!item.thread_id || drafting === item.thread_id}
                onClick={() => void draftReply(item)}
              >
                {drafting === item.thread_id ? 'Drafting…' : 'Draft reply'}
              </button>
            </article>
          ))
        )}
      </div>

      <div className="approval-note">
        Drafts land in Gmail for a final human review. Sending always requires a separate approval.
      </div>
    </div>
  );
}
