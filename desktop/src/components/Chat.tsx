import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../types';
import { friendlyChatError } from '../lib/chatErrors';

interface ChatProps {
  messages: ChatMessage[];
  streamText: string;
  processing: boolean;
  quickPrompts: string[];
  onSubmit: (text: string) => void;
  onNewChat: () => void;
  disabled: boolean;
}

function ErrorBlock({ content }: { content: string }) {
  const friendly = friendlyChatError(content);
  const [open, setOpen] = useState(false);

  return (
    <div className="chat-error-card">
      <div className="chat-error-title">{friendly.title}</div>
      <p className="chat-error-summary">{friendly.summary}</p>
      {friendly.detail && (
        <button
          type="button"
          className="chat-error-toggle"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? 'Hide details' : 'Show details'}
        </button>
      )}
      {open && friendly.detail && <pre className="chat-error-detail">{friendly.detail}</pre>}
    </div>
  );
}

export function Chat({
  messages,
  streamText,
  processing,
  quickPrompts,
  onSubmit,
  onNewChat,
  disabled,
}: ChatProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const starters = quickPrompts.slice(0, 3);
  const canNewChat = messages.length > 0 || Boolean(streamText);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, streamText, processing]);

  return (
    <div className="chat-page">
      <div className="chat-head">
        <div className="chat-head-row">
          <div>
            <h1>Chat</h1>
            <p>Ask HIVE to draft mail, schedule events, or run a workflow. Approvals still stop risky actions.</p>
          </div>
          <button
            type="button"
            className="btn btn-small"
            disabled={!canNewChat || processing}
            onClick={onNewChat}
            title="Clear this thread and start fresh"
          >
            New chat
          </button>
        </div>
      </div>

      <div className="chat-thread">
        {messages.length === 0 && !streamText && (
          <div className="chat-empty">
            <div className="chat-empty-title">Start with a club task</div>
            <p>Pick a starter, or type your own request below.</p>
            <div className="chat-suggestions">
              {starters.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="chat-suggestion"
                  disabled={disabled}
                  onClick={() => onSubmit(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => {
          if (message.role === 'error') {
            return (
              <div key={message.id} className="chat-row chat-row-error">
                <ErrorBlock content={message.content} />
              </div>
            );
          }

          const isUser = message.role === 'user';
          return (
            <div
              key={message.id}
              className={`chat-row ${isUser ? 'chat-row-user' : 'chat-row-assistant'}`}
            >
              <div className="chat-label">{isUser ? 'You' : 'HIVE'}</div>
              <div className={`chat-bubble ${isUser ? 'chat-user' : 'chat-assistant'}`}>
                {message.content}
              </div>
            </div>
          );
        })}

        {processing && (
          <div className="chat-row chat-row-assistant">
            <div className="chat-label">HIVE</div>
            <div className="chat-bubble chat-assistant chat-streaming">
              {streamText || 'Thinking…'}
              <span className="chat-cursor">▋</span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
