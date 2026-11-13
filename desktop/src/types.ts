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
