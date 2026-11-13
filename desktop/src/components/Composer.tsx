import { useState } from 'react';
import type { ConnectionState } from '../types';

interface ComposerProps {
  onSubmit: (text: string) => void;
  disabled: boolean;
  connected: ConnectionState;
  processing: boolean;
}

export function Composer({ onSubmit, disabled, connected, processing }: ComposerProps) {
  const [value, setValue] = useState('');

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    setValue('');
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="composer-prefix">›</div>
        <textarea
          className="composer-input"
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={
            connected !== 'connected'
              ? 'Waiting for the Python runtime…'
              : processing
                ? 'HIVE is working — watch the monitor…'
                : 'Give HIVE a mission. Enter to send, Shift+Enter for a new line.'
          }
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button className="send-btn" disabled={disabled || !value.trim()} onClick={submit}>
          {processing ? 'Running' : 'Send'}
        </button>
      </div>
      <div className="composer-hint">
        <span>
          {connected === 'connected'
            ? processing
              ? 'Execution in progress · approvals may interrupt'
              : 'Ready · leader routes single vs swarm automatically'
            : 'Runtime offline · restart from the sidebar'}
        </span>
        <span>Enter to send · Shift+Enter newline</span>
      </div>
    </div>
  );
}
