import { useCallback, useEffect, useState } from 'react';
import type { RequestFn } from '../types';
import { PageShell } from './PageShell';

export interface SetupStatus {
  ok: boolean;
  env_file?: string;
  llm_ready?: boolean;
  exa_ready?: boolean;
  google_client_ready?: boolean;
  spotify_client_ready?: boolean;
  google_connected?: boolean;
  google_email?: string | null;
  spotify_connected?: boolean;
  timezone?: string;
  model?: string;
  needs_setup?: boolean;
  fields?: Record<string, { set?: boolean; masked?: string; value?: string }>;
  error?: string;
}

interface SettingsProps {
  request: RequestFn;
  onRestart: () => void;
  onNotify?: (title: string, detail?: string) => void;
  onStatus?: (status: SetupStatus | null) => void;
}

type FormState = {
  HIVE_LLM_API_KEY: string;
  HIVE_LLM_BASE_URL: string;
  HIVE_LLM_MODEL: string;
  EXA_API_KEY: string;
  HIVE_TIMEZONE: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;
};

const EMPTY: FormState = {
  HIVE_LLM_API_KEY: '',
  HIVE_LLM_BASE_URL: '',
  HIVE_LLM_MODEL: '',
  EXA_API_KEY: '',
  HIVE_TIMEZONE: '',
  GOOGLE_CLIENT_ID: '',
  GOOGLE_CLIENT_SECRET: '',
  SPOTIFY_CLIENT_ID: '',
  SPOTIFY_CLIENT_SECRET: '',
};

export function Settings({ request, onRestart, onNotify, onStatus }: SettingsProps) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyStatus = useCallback(
    (next: SetupStatus) => {
      setStatus(next);
      onStatus?.(next);
      const fields = next.fields || {};
      setForm((prev) => ({
        ...prev,
        HIVE_LLM_BASE_URL: fields.HIVE_LLM_BASE_URL?.value || prev.HIVE_LLM_BASE_URL,
        HIVE_LLM_MODEL: fields.HIVE_LLM_MODEL?.value || prev.HIVE_LLM_MODEL,
        HIVE_TIMEZONE: fields.HIVE_TIMEZONE?.value || next.timezone || prev.HIVE_TIMEZONE,
        GOOGLE_CLIENT_ID: fields.GOOGLE_CLIENT_ID?.value || prev.GOOGLE_CLIENT_ID,
        SPOTIFY_CLIENT_ID: fields.SPOTIFY_CLIENT_ID?.value || prev.SPOTIFY_CLIENT_ID,
      }));
    },
    [onStatus]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await request('setup_status')) as SetupStatus;
      applyStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [applyStatus, request]);

  useEffect(() => {
    void load();
  }, [load]);

  const setField = (key: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setBusy('save');
    setMessage(null);
    setError(null);
    try {
      const values: Record<string, string> = {};
      (Object.keys(form) as Array<keyof FormState>).forEach((key) => {
        if (form[key].trim()) values[key] = form[key].trim();
      });
      const data = await request('save_secrets', { values });
      if (!data?.ok) {
        setError(data?.error || 'Could not save settings.');
        return;
      }
      if (data.status) applyStatus(data.status as SetupStatus);
      setMessage(data.message || 'Saved.');
      onNotify?.('Settings saved', data.message);
      setForm((prev) => ({
        ...prev,
        HIVE_LLM_API_KEY: '',
        EXA_API_KEY: '',
        GOOGLE_CLIENT_SECRET: '',
        SPOTIFY_CLIENT_SECRET: '',
      }));
      if (data.restart_required) onRestart();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const runConnect = async (action: string, label: string) => {
    setBusy(action);
    setMessage(null);
    setError(null);
    try {
      const data = await request(action, {}, 300000);
      if (!data?.ok) {
        setError(data?.error || `${label} failed.`);
        return;
      }
      if (data.status) applyStatus(data.status as SetupStatus);
      else await load();
      setMessage(data.message || `${label} done.`);
      onNotify?.(label, data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const fieldHint = (key: string, fallback: string) => {
    const meta = status?.fields?.[key];
    if (meta?.set && meta.masked) return `Saved · ${meta.masked}`;
    if (meta?.set) return 'Saved';
    return fallback;
  };

  return (
    <PageShell
      className="settings-page"
      title="Connections"
      purpose="Add keys once, connect Google and Spotify, then use Chat — no terminal."
      action={
        <button type="button" className="ghost-btn btn-small" onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      }
    >
      {status?.needs_setup && (
        <div className="banner banner-warn">
          <div>
            <strong>Add an AI key to unlock Chat.</strong> Everything else is optional until you need
            mail or music.
          </div>
        </div>
      )}

      {message && <div className="banner banner-ok">{message}</div>}
      {error && <div className="banner banner-error">{error}</div>}

      <div className="conn-status-bar">
        <span className={`connection-chip ${status?.llm_ready ? 'on' : ''}`}>
          <span className="status-dot" />
          AI {status?.llm_ready ? 'ready' : 'needed'}
        </span>
        <span className={`connection-chip ${status?.google_connected ? 'on' : ''}`}>
          <span className="status-dot" />
          Google {status?.google_connected ? 'connected' : 'off'}
        </span>
        <span className={`connection-chip ${status?.spotify_connected ? 'on' : ''}`}>
          <span className="status-dot" />
          Spotify {status?.spotify_connected ? 'connected' : 'off'}
        </span>
        <span className={`connection-chip ${status?.exa_ready ? 'on' : ''}`}>
          <span className="status-dot" />
          Search {status?.exa_ready ? 'ready' : 'off'}
        </span>
      </div>

      <div className="settings-stack">
        <section className="card conn-panel">
          <header className="conn-panel-head">
            <div>
              <h2 className="conn-title">AI model</h2>
              <p className="conn-sub">Required for chat. Groq, OpenRouter, DashScope, or any OpenAI-compatible key.</p>
            </div>
          </header>
          <div className="settings-grid">
            <label className="settings-field">
              <span>API key</span>
              <input
                type="password"
                autoComplete="off"
                placeholder={fieldHint('HIVE_LLM_API_KEY', 'Paste your API key')}
                value={form.HIVE_LLM_API_KEY}
                onChange={(e) => setField('HIVE_LLM_API_KEY', e.target.value)}
              />
            </label>
            <label className="settings-field">
              <span>Model</span>
              <input
                type="text"
                placeholder={fieldHint('HIVE_LLM_MODEL', 'e.g. openai/gpt-oss-20b')}
                value={form.HIVE_LLM_MODEL}
                onChange={(e) => setField('HIVE_LLM_MODEL', e.target.value)}
              />
            </label>
            <label className="settings-field">
              <span>Base URL</span>
              <input
                type="text"
                placeholder={fieldHint('HIVE_LLM_BASE_URL', 'https://api.groq.com/openai/v1')}
                value={form.HIVE_LLM_BASE_URL}
                onChange={(e) => setField('HIVE_LLM_BASE_URL', e.target.value)}
              />
            </label>
            <label className="settings-field">
              <span>Timezone</span>
              <input
                type="text"
                placeholder="Asia/Kolkata"
                value={form.HIVE_TIMEZONE}
                onChange={(e) => setField('HIVE_TIMEZONE', e.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="card conn-panel">
          <header className="conn-panel-head">
            <div>
              <h2 className="conn-title">Google</h2>
              <p className="conn-sub">Gmail + Calendar. Save client ID/secret, then connect in the browser.</p>
            </div>
            <span className={`connection-chip ${status?.google_connected ? 'on' : ''}`}>
              <span className="status-dot" />
              {status?.google_connected
                ? status.google_email || 'Connected'
                : status?.google_client_ready
                  ? 'Ready to connect'
                  : 'Not set'}
            </span>
          </header>
          <div className="settings-grid">
            <label className="settings-field">
              <span>Client ID</span>
              <input
                type="text"
                placeholder={fieldHint('GOOGLE_CLIENT_ID', '….apps.googleusercontent.com')}
                value={form.GOOGLE_CLIENT_ID}
                onChange={(e) => setField('GOOGLE_CLIENT_ID', e.target.value)}
              />
            </label>
            <label className="settings-field">
              <span>Client secret</span>
              <input
                type="password"
                autoComplete="off"
                placeholder={fieldHint('GOOGLE_CLIENT_SECRET', 'Paste client secret')}
                value={form.GOOGLE_CLIENT_SECRET}
                onChange={(e) => setField('GOOGLE_CLIENT_SECRET', e.target.value)}
              />
            </label>
          </div>
          <div className="card-actions">
            <button
              type="button"
              className="btn"
              disabled={Boolean(busy)}
              onClick={() => void runConnect('connect_google', 'Connect Google')}
            >
              {busy === 'connect_google' ? 'Waiting for browser…' : 'Connect Google'}
            </button>
            {status?.google_connected && (
              <button
                type="button"
                className="ghost-btn"
                disabled={Boolean(busy)}
                onClick={() => void runConnect('disconnect_google', 'Disconnect Google')}
              >
                Disconnect
              </button>
            )}
          </div>
        </section>

        <section className="card conn-panel">
          <header className="conn-panel-head">
            <div>
              <h2 className="conn-title">Spotify</h2>
              <p className="conn-sub">Playback control. Premium required. Save credentials, then connect.</p>
            </div>
            <span className={`connection-chip ${status?.spotify_connected ? 'on' : ''}`}>
              <span className="status-dot" />
              {status?.spotify_connected
                ? 'Connected'
                : status?.spotify_client_ready
                  ? 'Ready to connect'
                  : 'Not set'}
            </span>
          </header>
          <div className="settings-grid">
            <label className="settings-field">
              <span>Client ID</span>
              <input
                type="text"
                placeholder={fieldHint('SPOTIFY_CLIENT_ID', 'Spotify client ID')}
                value={form.SPOTIFY_CLIENT_ID}
                onChange={(e) => setField('SPOTIFY_CLIENT_ID', e.target.value)}
              />
            </label>
            <label className="settings-field">
              <span>Client secret</span>
              <input
                type="password"
                autoComplete="off"
                placeholder={fieldHint('SPOTIFY_CLIENT_SECRET', 'Paste client secret')}
                value={form.SPOTIFY_CLIENT_SECRET}
                onChange={(e) => setField('SPOTIFY_CLIENT_SECRET', e.target.value)}
              />
            </label>
          </div>
          <div className="card-actions">
            <button
              type="button"
              className="btn"
              disabled={Boolean(busy)}
              onClick={() => void runConnect('connect_spotify', 'Connect Spotify')}
            >
              {busy === 'connect_spotify' ? 'Waiting for browser…' : 'Connect Spotify'}
            </button>
            {status?.spotify_connected && (
              <button
                type="button"
                className="ghost-btn"
                disabled={Boolean(busy)}
                onClick={() => void runConnect('disconnect_spotify', 'Disconnect Spotify')}
              >
                Disconnect
              </button>
            )}
          </div>
        </section>

        <section className="card conn-panel">
          <header className="conn-panel-head">
            <div>
              <h2 className="conn-title">Web search</h2>
              <p className="conn-sub">Optional Exa key for live search from Chat.</p>
            </div>
            <span className={`connection-chip ${status?.exa_ready ? 'on' : ''}`}>
              <span className="status-dot" />
              {status?.exa_ready ? 'Ready' : 'Not set'}
            </span>
          </header>
          <div className="settings-grid settings-grid-one">
            <label className="settings-field">
              <span>Exa API key</span>
              <input
                type="password"
                autoComplete="off"
                placeholder={fieldHint('EXA_API_KEY', 'Paste Exa key')}
                value={form.EXA_API_KEY}
                onChange={(e) => setField('EXA_API_KEY', e.target.value)}
              />
            </label>
          </div>
        </section>

        <div className="settings-footer-actions">
          <button type="button" className="btn" disabled={Boolean(busy)} onClick={() => void save()}>
            {busy === 'save' ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className="ghost-btn" disabled={Boolean(busy)} onClick={onRestart}>
            Restart runtime
          </button>
        </div>
      </div>
    </PageShell>
  );
}
