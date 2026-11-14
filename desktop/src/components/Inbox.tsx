import { useCallback, useEffect, useState } from 'react';
import type { InboxItem, RequestFn } from '../types';
import { EmptyState, PageShell } from './PageShell';

interface InboxProps {
  request: RequestFn;
  refreshKey: number;
  onNotify: (kind: string, title: string, detail?: string) => void;
  onAsk?: (text: string) => void;
}

export function InboxScreen({ request, refreshKey, onNotify, onAsk }: InboxProps) {
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
    <PageShell
      className="ops-page"
      title="Inbox"
      purpose="Unread mail classified by urgency. Drafts are prepared for review — never auto-sent."
      meta={<span className="pending-pill">{unread} unread</span>}
      action={
        <button type="button" className="ghost-btn btn-small" onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      }
    >
      {needsAuth && (
        <div className="banner banner-warn">
          <div>
            <strong>Connect Google to read Gmail.</strong>
            <div className="card-foot" style={{ marginTop: 6 }}>
              Open Connections → Google, save your OAuth client, then click Connect Google.
            </div>
          </div>
        </div>
      )}

      {error && !needsAuth && <div className="banner banner-error">{error}</div>}

      <div className="item-list">
        {items.length === 0 && !loading ? (
          <EmptyState
            icon="✉"
            title="Inbox zero"
            body="No unread messages in the last 14 days. Run triage anytime or refresh after new mail arrives."
            actionLabel={onAsk ? 'Ask HIVE to triage inbox' : 'Refresh'}
            onAction={
              onAsk
                ? () => onAsk('Triage my unread inbox and draft replies for anything urgent.')
                : () => void load()
            }
          />
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
        Drafts land in Gmail for review. Sending always needs a separate approval.
      </div>
    </PageShell>
  );
}
