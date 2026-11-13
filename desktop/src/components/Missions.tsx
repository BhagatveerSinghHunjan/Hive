import { useCallback, useEffect, useState } from 'react';
import type { MissionInfo, RequestFn } from '../types';

interface MissionsProps {
  request: RequestFn;
  onNotify: (kind: string, title: string, detail?: string) => void;
  onAsk: (text: string) => void;
}

interface NextAction {
  tool: string;
  args?: Record<string, unknown>;
  reason?: string;
  requires_approval?: boolean;
}

function paramKeys(mission: MissionInfo): string[] {
  return Array.from(
    new Set([...(mission.required ?? []), ...Object.keys(mission.params ?? {})])
  );
}

export function MissionsScreen({ request, onNotify, onAsk }: MissionsProps) {
  const [missions, setMissions] = useState<MissionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [running, setRunning] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, Record<string, string>>>({});
  const [result, setResult] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('missions');
      setMissions(data.missions ?? []);
      if (!data.ok) setError(String(data.error ?? 'Missions unavailable'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = useCallback(
    async (mission: MissionInfo) => {
      setRunning(mission.name);
      setError('');
      setResult(null);
      try {
        const data = await request('mission_run', {
          name: mission.name,
          params: values[mission.name] ?? {},
        });
        setResult(data);
        onNotify(
          'response',
          `Mission: ${mission.title}`,
          data.ok ? 'Workflow finished — review next actions.' : String(data.error ?? 'Failed')
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setRunning(null);
      }
    },
    [onNotify, request, values]
  );

  const nextActions: NextAction[] = Array.isArray(result?.next_actions)
    ? result.next_actions
    : [];

  return (
    <div className="ops-page">
      <div className="page-head">
        <div>
          <h1>Missions</h1>
          <p>One click runs a club-ops workflow. Outbound actions come back as proposals for approval.</p>
        </div>
        <div className="page-head-actions">
          <span className="pending-pill">{missions.length} missions</span>
          <button className="ghost-btn" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="mission-grid">
        {missions.map((mission) => {
          const keys = paramKeys(mission);
          const isActive = active === mission.name;
          return (
            <article key={mission.name} className={`mission-card ${isActive ? 'active' : ''}`}>
              <div className="mission-card-head">
                <div>
                  <div className="card-label">{mission.source === 'custom' ? 'Custom' : 'Built-in'}</div>
                  <h3>{mission.title}</h3>
                </div>
                <span className="tag">{mission.workflow}</span>
              </div>
              <p className="mission-copy">{mission.description}</p>

              {isActive && keys.length > 0 && (
                <div className="mission-params">
                  {keys.map((key) => (
                    <label key={key} className="mission-field">
                      <span>{key}</span>
                      <input
                        className="text-input"
                        value={values[mission.name]?.[key] ?? ''}
                        placeholder={String(mission.params?.[key] ?? '')}
                        onChange={(event) =>
                          setValues((prev) => ({
                            ...prev,
                            [mission.name]: {
                              ...(prev[mission.name] ?? {}),
                              [key]: event.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                  ))}
                </div>
              )}

              <div className="mission-actions">
                <button
                  className="btn btn-approve"
                  disabled={running === mission.name}
                  onClick={() => void run(mission)}
                >
                  {running === mission.name ? 'Running…' : 'Run mission'}
                </button>
                <button className="ghost-btn" onClick={() => setActive(isActive ? null : mission.name)}>
                  {isActive ? 'Hide params' : keys.length > 0 ? 'Set params' : 'Details'}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {result && (
        <section className="mission-result card">
          <div className="card-row">
            <div>
              <div className="card-label">Latest result</div>
              <h3>{result.title ?? result.mission ?? 'Mission'}</h3>
            </div>
            <span className={`tier-badge ${result.ok ? 'tier-safe' : 'tier-dangerous'}`}>
              {result.ok ? 'ok' : 'attention'}
            </span>
          </div>

          {result.summary && <pre className="mission-summary">{result.summary}</pre>}
          {result.error && <div className="banner banner-error">{result.error}</div>}

          {nextActions.length > 0 && (
            <div className="next-actions">
              <div className="card-label">Next actions</div>
              {nextActions.map((action, index) => (
                <div key={`${action.tool}-${index}`} className="next-action">
                  <div className="next-action-main">
                    <div className="next-action-head">
                      <code>{action.tool}</code>
                      {action.requires_approval && (
                        <span className="tier-badge tier-sensitive">needs approval</span>
                      )}
                    </div>
                    {action.reason && <p>{action.reason}</p>}
                    {action.args && (
                      <pre className="args">{JSON.stringify(action.args, null, 2)}</pre>
                    )}
                  </div>
                  <button
                    className="btn btn-small btn-approve"
                    onClick={() =>
                      onAsk(
                        `Execute this prepared action now: tool ${action.tool}, args ${JSON.stringify(
                          action.args ?? {}
                        )}. This is a proposal from a club-ops mission; request human approval before any outbound action.`
                      )
                    }
                  >
                    Ask HIVE to run
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
