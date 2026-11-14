import { useState } from 'react';
import type { InteractivePromptRequest, PermissionRequest } from '../types';
import { EmptyState, PageShell } from './PageShell';

interface ApprovalsProps {
  approvals: PermissionRequest[];
  interactive: InteractivePromptRequest[];
  onPermission: (requestId: string, decision: 'approved' | 'denied') => void;
  onInteractive: (requestId: string, result: unknown) => void;
}

const TOOL_INFO: Record<string, { question: string; note: string }> = {
  gmail_create_draft: {
    question: 'Create this Gmail draft?',
    note: 'Draft only — nothing is sent until you approve a send later.',
  },
  gmail_send_draft: {
    question: 'Send this email?',
    note: 'This delivers the draft to the recipient.',
  },
  gmail_send_message: {
    question: 'Send this email?',
    note: 'This delivers a message to the recipient.',
  },
  calendar_create_event: {
    question: 'Create this calendar event?',
    note: 'Attendees may receive an invite.',
  },
  calendar_update_event: {
    question: 'Update this calendar event?',
    note: 'Attendees may be notified of the change.',
  },
  calendar_delete_event: {
    question: 'Delete this calendar event?',
    note: 'This removes the event and may notify attendees.',
  },
  browser_playbook_replay: {
    question: 'Replay this browser playbook?',
    note: 'Trust level decides how much of this site run needs approval.',
  },
  checkout_confirm: {
    question: 'Confirm this purchase?',
    note: 'Review merchant and amount before approving.',
  },
};

function toolInfo(tool: string) {
  return (
    TOOL_INFO[tool] ?? {
      question: `Allow ${tool}?`,
      note: 'Review the target carefully before approving.',
    }
  );
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
          <div className="card-label">Needs your decision</div>
          <h3>{info.question}</h3>
          <div className="approval-tool">{request.tool}</div>
        </div>
        <span className={`tier-badge ${tierClass(request.tier)}`}>{request.tier}</span>
      </div>

      <div className="approval-target">
        <span>Details</span>
        <code>{request.target || '(no target)'}</code>
      </div>

      <p className="approval-copy">{info.note}</p>

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
      ? 'Enter the verification code'
      : prompt.kind === 'checkout_confirm'
        ? 'Confirm this purchase?'
        : 'Solve the CAPTCHA, then confirm';

  return (
    <article className="approval-card approval-interactive">
      <div className="approval-head">
        <div>
          <div className="card-label">Needs your input</div>
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
    <PageShell
      className="approvals"
      title="Approvals"
      purpose="HIVE pauses here before sending mail or changing your calendar."
      meta={
        <div className={`pending-pill ${pending > 0 ? 'has-pending' : ''}`}>
          {pending > 0 ? `${pending} waiting` : 'all clear'}
        </div>
      }
    >
      {pending === 0 ? (
        <EmptyState
          icon="✓"
          title="Nothing waiting"
          body="Safe reads run automatically. Sends, calendar writes, and risky tools pause here for you."
        />
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

      {pending === 0 && (
        <div className="risk-legend" style={{ marginTop: 16, justifyContent: 'center' }}>
          <span className="tier-badge tier-safe">safe</span>
          <span className="tier-badge tier-moderate">moderate</span>
          <span className="tier-badge tier-sensitive">sensitive</span>
          <span className="tier-badge tier-dangerous">dangerous</span>
        </div>
      )}

      <div className="approval-note">
        Permission prompts time out after 120s. Denying is always safe — HIVE adapts.
      </div>
    </PageShell>
  );
}
