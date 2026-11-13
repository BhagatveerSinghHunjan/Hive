import { useState } from 'react';
import type { InteractivePromptRequest, PermissionRequest } from '../types';

interface ApprovalsProps {
  approvals: PermissionRequest[];
  interactive: InteractivePromptRequest[];
  onPermission: (requestId: string, decision: 'approved' | 'denied') => void;
  onInteractive: (requestId: string, result: unknown) => void;
}

const TOOL_INFO: Record<string, { label: string; note: string }> = {
  gmail_create_draft: {
    label: 'Create Gmail draft',
    note: 'Draft only — nothing is sent until you send it from Gmail or approve a send.',
  },
  gmail_send_draft: {
    label: 'Send Gmail draft',
    note: 'This will deliver an email to the recipient shown above.',
  },
  gmail_send_message: {
    label: 'Send Gmail message',
    note: 'This will deliver an email to the recipient shown above.',
  },
  calendar_create_event: {
    label: 'Create calendar event',
    note: 'Attendees will receive an invite for the event shown above.',
  },
  calendar_update_event: {
    label: 'Update calendar event',
    note: 'This changes an existing event. Attendees may be notified.',
  },
  calendar_delete_event: {
    label: 'Delete calendar event',
    note: 'This removes an event and may notify attendees.',
  },
  browser_playbook_replay: {
    label: 'Replay a browser playbook',
    note: 'Trust level decides whether this step needs approval for the site shown above.',
  },
  checkout_confirm: {
    label: 'Confirm purchase',
    note: 'Review the merchant and amount before approving.',
  },
};

function toolInfo(tool: string) {
  return TOOL_INFO[tool] ?? { label: tool, note: 'Review the target carefully before approving.' };
}

function tierClass(tier: string): string {
  const value = tier.toLowerCase();
  if (value === 'dangerous') return 'tier-dangerous';
  if (value === 'sensitive') return 'tier-sensitive';
  if (value === 'moderate') return 'tier-moderate';
  return 'tier-safe';
}

function PermissionCard({
  request,
  onDecision,
}: {
  request: PermissionRequest;
  onDecision: (requestId: string, decision: 'approved' | 'denied') => void;
}) {
  const info = toolInfo(request.tool);

  return (
    <article className="approval-card">
      <div className="approval-head">
        <div>
          <div className="card-label">Permission request</div>
          <h3>{info.label}</h3>
          <div className="approval-tool">{request.tool}</div>
        </div>
        <span className={`tier-badge ${tierClass(request.tier)}`}>{request.tier}</span>
      </div>

      <div className="approval-target">
        <span>Prepared change</span>
        <code>{request.target || '(no target)'}</code>
      </div>

      <p className="approval-copy">{info.note}</p>
      <p className="approval-copy">
        Approve only if the target and tier look right. The runtime waits up to 120 seconds.
      </p>

      <div className="approval-actions">
        <button className="btn btn-deny" onClick={() => onDecision(request.request_id, 'denied')}>
          Deny
        </button>
        <button className="btn btn-approve" onClick={() => onDecision(request.request_id, 'approved')}>
          Approve
        </button>
      </div>
    </article>
  );
}

function InteractiveCard({
  prompt,
  onDecision,
}: {
  prompt: InteractivePromptRequest;
  onDecision: (requestId: string, result: unknown) => void;
}) {
  const [code, setCode] = useState('');

  const title =
    prompt.kind === '2fa'
      ? 'Verification code required'
      : prompt.kind === 'checkout_confirm'
        ? 'Confirm purchase'
        : 'CAPTCHA — human required';

  return (
    <article className="approval-card approval-interactive">
      <div className="approval-head">
        <div>
          <div className="card-label">Human input</div>
          <h3>{title}</h3>
        </div>
        <span className="tier-badge tier-human">human</span>
      </div>

      <div className="approval-target">
        <span>Site</span>
        <code>{prompt.site || prompt.url || 'unknown'}</code>
      </div>

      {prompt.message && <p className="approval-copy">{prompt.message}</p>}

      {prompt.kind === '2fa' && (
        <div className="interactive-body">
          <label className="field-label" htmlFor={`code-${prompt.request_id}`}>
            One-time code
          </label>
          <input
            id={`code-${prompt.request_id}`}
            className="text-input code-input"
            inputMode="numeric"
            autoFocus
            maxLength={8}
            placeholder="123456"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 8))}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && code.trim()) {
                onDecision(prompt.request_id, code.trim());
              }
            }}
          />
          <div className="approval-actions">
            <button className="btn btn-deny" onClick={() => onDecision(prompt.request_id, null)}>
              Cancel
            </button>
            <button
              className="btn btn-approve"
              disabled={!code.trim()}
              onClick={() => onDecision(prompt.request_id, code.trim())}
            >
              Submit code
            </button>
          </div>
        </div>
      )}

      {prompt.kind === 'checkout_confirm' && (
        <div className="interactive-body">
          <div className="checkout-line">
            <span>{prompt.merchant || 'Merchant'}</span>
            <strong>${typeof prompt.amount === 'number' ? prompt.amount.toFixed(2) : 'unknown'}</strong>
          </div>
          <p className="approval-copy">
            HIVE stops before placing the order. Confirm only if the amount and merchant are correct.
          </p>
          <div className="approval-actions">
            <button className="btn btn-deny" onClick={() => onDecision(prompt.request_id, false)}>
              Cancel
            </button>
            <button className="btn btn-approve" onClick={() => onDecision(prompt.request_id, true)}>
              Confirm purchase
            </button>
          </div>
        </div>
      )}

      {prompt.kind === 'captcha_handoff' && (
        <div className="interactive-body">
          <p className="approval-copy">
            Solve the CAPTCHA in the browser window, then confirm here. HIVE resumes after your confirmation.
          </p>
          <div className="approval-actions">
            <button className="btn btn-deny" onClick={() => onDecision(prompt.request_id, false)}>
              Cancel
            </button>
            <button className="btn btn-approve" onClick={() => onDecision(prompt.request_id, true)}>
              I solved it
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function Approvals({ approvals, interactive, onPermission, onInteractive }: ApprovalsProps) {
  const pending = approvals.length + interactive.length;

  return (
    <div className="approvals">
      <div className="page-head">
        <div>
          <h1>Approvals</h1>
          <p>Human-in-the-loop gates for risky tools, money, and identity.</p>
        </div>
        <div className={`pending-pill ${pending > 0 ? 'has-pending' : ''}`}>
          {pending > 0 ? `${pending} waiting` : 'all clear'}
        </div>
      </div>

      {pending === 0 ? (
        <div className="empty approval-empty">
          <div className="empty-icon">⬡</div>
          <h2>No approvals waiting</h2>
          <p>
            When HIVE wants to edit a file, run a sensitive command, confirm a purchase, or hand over a 2FA code, the request
            lands here. Safe reads are auto-approved.
          </p>
          <div className="risk-legend">
            <span className="tier-badge tier-safe">safe</span>
            <span className="tier-badge tier-moderate">moderate</span>
            <span className="tier-badge tier-sensitive">sensitive</span>
            <span className="tier-badge tier-dangerous">dangerous</span>
          </div>
        </div>
      ) : (
        <div className="approval-list">
          {approvals.map((request) => (
            <PermissionCard key={request.request_id} request={request} onDecision={onPermission} />
          ))}
          {interactive.map((prompt) => (
            <InteractiveCard key={prompt.request_id} prompt={prompt} onDecision={onInteractive} />
          ))}
        </div>
      )}

      <div className="approval-note">
        Permission prompts time out after 120s; human prompts after 600s. Denying is always safe — HIVE adapts.
      </div>
    </div>
  );
}
