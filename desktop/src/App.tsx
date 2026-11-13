import { useCallback, useEffect, useRef, useState } from 'react';
import { Header } from './components/Header';
import { Nav, type Screen } from './components/Nav';
import { Dashboard } from './components/Dashboard';
import { Monitor } from './components/Monitor';
import { Approvals } from './components/Approvals';
import { Composer } from './components/Composer';
import { InboxScreen } from './components/Inbox';
import { CalendarScreen } from './components/Calendar';
import { TasksScreen } from './components/Tasks';
import { MissionsScreen } from './components/Missions';
import { EggToast } from './components/EggToast';
import type {
  AgentState,
  Budget,
  ChatMessage,
  ConnectionState,
  HiveEvent,
  InteractivePromptRequest,
  OverviewData,
  PermissionRequest,
  RequestFn,
  TimelineEvent,
  ToolCall,
} from './types';

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `hive-${idCounter}`;
}

const QUICK_PROMPTS = [
  'Triage my unread inbox and draft replies for anything urgent.',
  'Prep me for my next club meeting using my calendar and email.',
  'Remind sponsors about outstanding deliverables — draft the emails first.',
  'Give me my morning brief: agenda, unread email, and tasks due soon.',
];

export default function App() {
  const [screen, setScreen] = useState<Screen>('dashboard');
  const [connected, setConnected] = useState<ConnectionState>('connecting');
  const [status, setStatus] = useState('connecting');
  const [task, setTask] = useState('');
  const [mode, setMode] = useState('auto');
  const [elapsed, setElapsed] = useState('0.0s');
  const [budget, setBudget] = useState<Budget>({ spent: 0, total: 1000 });
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [subtasks, setSubtasks] = useState({ done: 0, total: 0 });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamText, setStreamText] = useState('');
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [approvals, setApprovals] = useState<PermissionRequest[]>([]);
  const [interactiveQueue, setInteractiveQueue] = useState<InteractivePromptRequest[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [processing, setProcessing] = useState(false);
  const [runtimeExit, setRuntimeExit] = useState<string | null>(null);
  const [apiKeyIssue, setApiKeyIssue] = useState(false);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [eggMessage, setEggMessage] = useState<string | null>(null);
  const eggTimer = useRef<number | null>(null);

  const showEgg = useCallback((message: string) => {
    if (eggTimer.current !== null) window.clearTimeout(eggTimer.current);
    setEggMessage(message);
    eggTimer.current = window.setTimeout(() => setEggMessage(null), 3200);
  }, []);

  const streamBuffer = useRef('');
  const flushTimer = useRef<number | null>(null);
  const pendingRequests = useRef(
    new Map<string, { resolve: (data: any) => void; timer: number }>()
  );
  const connectedRef = useRef<ConnectionState>('connecting');

  useEffect(() => {
    connectedRef.current = connected;
  }, [connected]);

  const request = useCallback<RequestFn>((action, params = {}) => {
    return new Promise((resolve, reject) => {
      if (connectedRef.current !== 'connected') {
        reject(new Error('Python runtime is not connected.'));
        return;
      }
      const requestId = nextId();
      const timer = window.setTimeout(() => {
        pendingRequests.current.delete(requestId);
        reject(new Error(`Request timed out: ${action}`));
      }, 120000);
      pendingRequests.current.set(requestId, { resolve, timer });
      window.hive.send({ type: 'request', request_id: requestId, action, params });
    });
  }, []);

  const loadOverview = useCallback(async () => {
    try {
      const data = await request('overview');
      setOverview(
        data && data.inbox && data.agenda && data.tasks ? (data as OverviewData) : null
      );
    } catch {
      // overview failures surface inside the dashboard cards
    }
  }, [request]);

  const pushEvent = useCallback((kind: string, title: string, detail?: string) => {
    setEvents((prev) => {
      const next = [...prev, { id: nextId(), ts: Date.now(), kind, title, detail }];
      return next.length > 200 ? next.slice(-200) : next;
    });
  }, []);

  const stopStream = useCallback(() => {
    if (flushTimer.current !== null) {
      window.clearInterval(flushTimer.current);
      flushTimer.current = null;
    }
    if (streamBuffer.current) {
      const chunk = streamBuffer.current;
      streamBuffer.current = '';
      setStreamText((prev) => (prev + chunk).slice(-20000));
    }
  }, []);

  const startStream = useCallback(() => {
    if (flushTimer.current !== null) return;
    flushTimer.current = window.setInterval(() => {
      if (!streamBuffer.current) return;
      const chunk = streamBuffer.current;
      streamBuffer.current = '';
      setStreamText((prev) => (prev + chunk).slice(-20000));
    }, 80);
  }, []);

  useEffect(() => {
    const onEvent = (raw: HiveEvent) => {
      if (raw.type === 'response' && typeof raw.request_id === 'string') {
        const pending = pendingRequests.current.get(raw.request_id);
        if (pending) {
          window.clearTimeout(pending.timer);
          pendingRequests.current.delete(raw.request_id);
          pending.resolve(raw.data ?? { ok: raw.ok === true });
          return;
        }
      }

      switch (raw.type) {
        case 'ready':
          connectedRef.current = 'connected';
          setConnected('connected');
          setStatus('idle');
          setRuntimeExit(null);
          setApiKeyIssue(false);
          pushEvent('system', 'Runtime connected', 'Electron ↔ JSON-lines ↔ Python');
          void loadOverview();
          break;

        case 'state':
          setOverview((raw.state as OverviewData) ?? null);
          break;

        case 'tasks_updated':
          setRefreshTick((value) => value + 1);
          void loadOverview();
          break;

        case 'inbox_updated':
          setRefreshTick((value) => value + 1);
          void loadOverview();
          break;

        case 'stream': {
          const token = String(raw.content ?? '');
          if (!token) break;
          streamBuffer.current += token;
          startStream();
          break;
        }

        case 'tool_call': {
          const tool = String(raw.tool ?? 'tool');
          const args = (raw.args as Record<string, unknown>) ?? {};
          setToolCalls((prev) => {
            const next = [...prev, { id: nextId(), tool, args, ts: Date.now() }];
            return next.length > 50 ? next.slice(-50) : next;
          });
          setStatus(`running ${tool}`);
          pushEvent('tool', tool, JSON.stringify(args).slice(0, 800));
          break;
        }

        case 'permission_request': {
          const request = raw as unknown as PermissionRequest;
          setApprovals((prev) => [...prev, request]);
          setScreen('approvals');
          pushEvent('approval', `Permission: ${request.tool}`, request.target);
          break;
        }

        case 'interactive_prompt': {
          const prompt = raw as unknown as InteractivePromptRequest;
          setInteractiveQueue((prev) => [...prev, prompt]);
          setScreen('approvals');
          pushEvent('approval', `Human input: ${prompt.kind}`, prompt.site || prompt.merchant || '');
          break;
        }

        case 'status':
          setStatus(String(raw.status ?? 'idle'));
          break;

        case 'mode':
          setMode(String(raw.mode ?? 'auto'));
          break;

        case 'elapsed':
          setElapsed(String(raw.elapsed ?? '0.0s'));
          break;

        case 'subtask_progress':
          setSubtasks({
            done: Number(raw.done ?? 0),
            total: Number(raw.total ?? 0),
          });
          break;

        case 'agent_spawn': {
          const id = String(raw.agent_id ?? nextId());
          const kind = String(raw.kind ?? 'worker');
          setAgents((prev) => {
            const without = prev.filter((a) => a.id !== id);
            return [...without, { id, kind, status: 'spawning', task: '' }];
          });
          pushEvent('agent', `Agent spawned: ${kind}`, id);
          break;
        }

        case 'agent_work': {
          const id = String(raw.agent_id ?? '');
          const agentTask = String(raw.task ?? '');
          setAgents((prev) =>
            prev.map((a) => (a.id === id ? { ...a, status: 'working', task: agentTask } : a))
          );
          pushEvent('agent', 'Agent working', agentTask || id);
          break;
        }

        case 'agent_done': {
          const id = String(raw.agent_id ?? '');
          setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, status: 'done' } : a)));
          pushEvent('agent', 'Agent done', id);
          break;
        }

        case 'agent_fail': {
          const id = String(raw.agent_id ?? '');
          const reason = String(raw.reason ?? '');
          setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, status: 'failed' } : a)));
          pushEvent('error', 'Agent failed', reason || id);
          break;
        }

        case 'spend': {
          const amount = Number(raw.amount ?? 0);
          setBudget((prev) => ({ ...prev, spent: prev.spent + amount }));
          pushEvent('credit', `Spent ${amount} credits`, String(raw.reason ?? ''));
          break;
        }

        case 'earn': {
          const amount = Number(raw.amount ?? 0);
          setBudget((prev) => ({ ...prev, spent: Math.max(0, prev.spent - amount) }));
          pushEvent('credit', `Earned ${amount} credits`, String(raw.reason ?? ''));
          break;
        }

        case 'response': {
          const content = String(raw.content ?? '');
          stopStream();
          setStreamText('');
          setMessages((prev) => {
            const next = [...prev, { id: nextId(), role: 'assistant' as const, content, ts: Date.now() }];
            return next.length > 50 ? next.slice(-50) : next;
          });
          setProcessing(false);
          setStatus('idle');
          setApprovals([]);
          setInteractiveQueue([]);
          pushEvent('response', 'Run complete', content.slice(0, 500));
          break;
        }

        case 'error': {
          const message = String(raw.message ?? 'Unknown runtime error');
          if (/invalid[_ -]?api[_ -]?key|incorrect api key/i.test(message)) {
            setApiKeyIssue(true);
          }
          stopStream();
          setStreamText('');
          setMessages((prev) => {
            const next = [...prev, { id: nextId(), role: 'error' as const, content: message, ts: Date.now() }];
            return next.length > 50 ? next.slice(-50) : next;
          });
          setProcessing(false);
          setStatus('error');
          setApprovals([]);
          setInteractiveQueue([]);
          pushEvent('error', 'Runtime error', message);
          break;
        }

        default:
          setLogs((prev) => [...prev.slice(-199), `[event] ${JSON.stringify(raw).slice(0, 300)}`]);
      }
    };

    const offEvent = window.hive.onEvent(onEvent);

    const offLog = window.hive.onLog((line) => {
      setLogs((prev) => {
        const next = [...prev, line];
        return next.length > 200 ? next.slice(-200) : next;
      });
    });

    const offExit = window.hive.onExit((info: any) => {
      const detail = info?.error
        ? String(info.error)
        : `Python exited (code ${info?.code ?? '?'}${info?.signal ? `, ${info.signal}` : ''})`;
      connectedRef.current = 'exited';
      setConnected('exited');
      setProcessing(false);
      setStatus('runtime exited');
      setRuntimeExit(detail);
      pushEvent('error', 'Python runtime exited', detail);
    });

    window.hive.ready();

    return () => {
      offEvent();
      offLog();
      offExit();
      if (flushTimer.current !== null) {
        window.clearInterval(flushTimer.current);
        flushTimer.current = null;
      }
      for (const pending of pendingRequests.current.values()) {
        window.clearTimeout(pending.timer);
      }
      pendingRequests.current.clear();
    };
  }, [loadOverview, pushEvent, startStream, stopStream]);

  // Dev-only harness for UI smoke tests. Vite strips this from production builds.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const demo = {
      approval: () => {
        setApprovals([
          {
            type: 'permission_request' as const,
            tool: 'write_file',
            target: 'C:\\Users\\lokes\\OneDrive\\Desktop\\PEC\\Hive\\hive-demo.md',
            tier: 'moderate',
            request_id: 'demo-approval',
          },
        ]);
        setScreen('approvals');
      },
      interactive: () => {
        setInteractiveQueue([
          {
            type: 'interactive_prompt' as const,
            kind: '2fa' as const,
            request_id: 'demo-2fa',
            site: 'github.com',
            message: 'Enter the code from your authenticator app.',
          },
        ]);
        setScreen('approvals');
      },
      stream: () => {
        setProcessing(true);
        setStatus('routing');
        setStreamText('HIVE is assembling a society of specialists...\n');
        pushEvent('system', 'Demo event stream', 'synthetic dev-only event');
      },
      reset: () => {
        setApprovals([]);
        setInteractiveQueue([]);
        setStreamText('');
        setProcessing(false);
        setStatus('idle');
        setScreen('dashboard');
      },
    };
    const demoWindow = window as unknown as { __hiveDemo?: typeof demo };
    demoWindow.__hiveDemo = demo;
    return () => {
      delete demoWindow.__hiveDemo;
    };
  }, [pushEvent]);

  const submit = useCallback(
    (text: string) => {
      const value = text.trim();
      if (!value || processing || connected !== 'connected') return;

      const secret = value.toLowerCase();
      if (secret === 'buzz' || secret === 'nectar' || secret === 'queen') {
        const lines: Record<string, string> = {
          buzz: 'Wings up. The colony heard that.',
          nectar: 'Credits are nectar. Spend them wisely.',
          queen: 'HiveCore is the queen — specialists are the comb.',
        };
        showEgg(lines[secret]);
        return;
      }

      setTask(value);
      setProcessing(true);
      setStatus('routing');
      setElapsed('0.0s');
      setStreamText('');
      streamBuffer.current = '';
      setToolCalls([]);
      setAgents([]);
      setSubtasks({ done: 0, total: 0 });
      setApprovals([]);
      setInteractiveQueue([]);
      setRuntimeExit(null);

      setMessages((prev) => {
        const next = [...prev, { id: nextId(), role: 'user' as const, content: value, ts: Date.now() }];
        return next.length > 50 ? next.slice(-50) : next;
      });
      pushEvent('user', 'You', value);
      window.hive.send({ type: 'user_message', content: value });
    },
    [connected, processing, pushEvent, showEgg]
  );

  const ask = useCallback(
    (text: string) => {
      setScreen('monitor');
      submit(text);
    },
    [submit]
  );

  const restart = useCallback(async () => {
    connectedRef.current = 'connecting';
    setConnected('connecting');
    setStatus('restarting');
    setRuntimeExit(null);
    setApiKeyIssue(false);
    setProcessing(false);
    setStreamText('');
    streamBuffer.current = '';
    setToolCalls([]);
    setAgents([]);
    setApprovals([]);
    setInteractiveQueue([]);
    setSubtasks({ done: 0, total: 0 });
    pushEvent('system', 'Restarting Python runtime');
    await window.hive.restart();
  }, [pushEvent]);

  const decidePermission = useCallback(
    (requestId: string, decision: 'approved' | 'denied') => {
      window.hive.send({ type: 'permission_response', request_id: requestId, decision });
      const remaining = approvals.filter((r) => r.request_id !== requestId).length;
      setApprovals((prev) => prev.filter((r) => r.request_id !== requestId));
      pushEvent('approval', `Permission ${decision}`, requestId);
      if (processing && remaining === 0 && interactiveQueue.length === 0) {
        setScreen('monitor');
      }
    },
    [approvals, interactiveQueue, processing, pushEvent]
  );

  const respondInteractive = useCallback(
    (requestId: string, result: unknown) => {
      window.hive.send({ type: 'interactive_response', request_id: requestId, result });
      const remaining = interactiveQueue.filter((r) => r.request_id !== requestId).length;
      setInteractiveQueue((prev) => prev.filter((r) => r.request_id !== requestId));
      pushEvent('approval', 'Human input submitted', requestId);
      if (processing && approvals.length === 0 && remaining === 0) {
        setScreen('monitor');
      }
    },
    [approvals, interactiveQueue, processing, pushEvent]
  );

  const latestAssistant = [...messages].reverse().find((m) => m.role === 'assistant');

  return (
    <div className="app">
      <Nav
        screen={screen}
        setScreen={setScreen}
        pendingApprovals={approvals.length + interactiveQueue.length}
        inboxCount={overview?.inbox.count ?? 0}
        taskCount={overview?.tasks.pending ?? 0}
        connected={connected}
        budget={budget}
        onRestart={restart}
        onEgg={showEgg}
      />

      <div className="workspace">
        <Header
          connected={connected}
          status={status}
          task={task}
          elapsed={elapsed}
          mode={mode}
          onRestart={restart}
        />

        {runtimeExit && (
          <div className="banner banner-error">
            <div>
              <strong>Python runtime exited.</strong> {runtimeExit}
            </div>
            <button className="btn btn-warn" onClick={restart}>
              Restart runtime
            </button>
          </div>
        )}

        {apiKeyIssue && !runtimeExit && (
          <div className="banner banner-warn">
            <div>
              <strong>Qwen API key rejected.</strong> Update <code>DASHSCOPE_API_KEY</code> in the repo{' '}
              <code>.env</code>, then restart the runtime.
            </div>
            <button className="btn btn-warn" onClick={restart}>
              Restart runtime
            </button>
          </div>
        )}

        <main className="screen">
          {screen === 'dashboard' && (
            <Dashboard
              connected={connected}
              status={status}
              task={task}
              mode={mode}
              elapsed={elapsed}
              budget={budget}
              agents={agents}
              subtasks={subtasks}
              events={events}
              messages={messages}
              latestAssistant={latestAssistant}
              processing={processing}
              quickPrompts={QUICK_PROMPTS}
              overview={overview}
              pendingApprovals={approvals.length + interactiveQueue.length}
              onOpen={setScreen}
              onRefresh={loadOverview}
              onSubmit={submit}
            />
          )}

          {screen === 'inbox' && (
            <InboxScreen request={request} refreshKey={refreshTick} onNotify={pushEvent} />
          )}

          {screen === 'calendar' && (
            <CalendarScreen request={request} refreshKey={refreshTick} onAsk={ask} />
          )}

          {screen === 'tasks' && (
            <TasksScreen request={request} refreshKey={refreshTick} onNotify={pushEvent} />
          )}

          {screen === 'missions' && (
            <MissionsScreen request={request} onNotify={pushEvent} onAsk={ask} />
          )}

          {screen === 'monitor' && (
            <Monitor
              events={events}
              agents={agents}
              toolCalls={toolCalls}
              streamText={streamText}
              processing={processing}
              logs={logs}
            />
          )}

          {screen === 'approvals' && (
            <Approvals
              approvals={approvals}
              interactive={interactiveQueue}
              onPermission={decidePermission}
              onInteractive={respondInteractive}
            />
          )}
        </main>

        <Composer
          onSubmit={submit}
          disabled={processing || connected !== 'connected'}
          connected={connected}
          processing={processing}
        />
      </div>

      <EggToast message={eggMessage} />
    </div>
  );
}
