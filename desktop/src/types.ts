export type ConnectionState = 'connecting' | 'connected' | 'exited';

export interface AgentState {
  id: string;
  kind: string;
  status: 'spawning' | 'working' | 'done' | 'failed';
  task: string;
}

export interface PermissionRequest {
  type: 'permission_request';
  tool: string;
  target: string;
  tier: string;
  request_id: string;
}

export interface InteractivePromptRequest {
  type: 'interactive_prompt';
  kind: '2fa' | 'checkout_confirm' | 'captcha_handoff';
  request_id: string;
  site?: string;
  message?: string;
  amount?: number;
  merchant?: string;
  url?: string;
}

export interface HiveEvent {
  type: string;
  [key: string]: unknown;
}

export interface TimelineEvent {
  id: string;
  ts: number;
  kind: string;
  title: string;
  detail?: string;
}

export interface ToolCall {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  ts: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  ts: number;
}

export interface Budget {
  spent: number;
  total: number;
}

export interface InboxItem {
  message_id?: string;
  thread_id?: string;
  from: string;
  subject: string;
  date?: string;
  snippet?: string;
  unread?: boolean;
  priority: 'high' | 'medium' | 'low';
  categories?: string[];
  needs_reply?: boolean;
}

export interface AgendaEvent {
  event_id?: string;
  summary: string;
  start: string;
  end?: string;
  location?: string;
  description?: string;
  html_link?: string;
  meet_link?: string;
  attendees?: Array<{ email?: string; name?: string; status?: string }>;
}

export interface TaskItem {
  task_id: string;
  title: string;
  notes?: string;
  due?: string | null;
  priority?: 'high' | 'medium' | 'low';
  status: 'pending' | 'done';
  source?: string;
}

export interface MissionInfo {
  name: string;
  title: string;
  description?: string;
  workflow: string;
  params?: Record<string, unknown>;
  required?: string[];
  source?: string;
}

export interface OverviewData {
  ok: boolean;
  timezone?: string;
  inbox: { ok: boolean; count: number; needs_auth?: boolean; items: InboxItem[] };
  agenda: {
    ok: boolean;
    count: number;
    next?: AgendaEvent | null;
    events: AgendaEvent[];
    needs_auth?: boolean;
  };
  tasks: { ok: boolean; pending: number; due_soon: TaskItem[] };
  missions: number;
  connections: {
    google_connected: boolean;
    google_email?: string | null;
    slack_configured: boolean;
  };
}

export type RequestFn = (action: string, params?: Record<string, unknown>) => Promise<any>;
