import { useEffect, useRef, useState } from 'react';
import type { ConnectionState } from '../types';

interface ComposerProps {
  onSubmit: (text: string) => void;
  disabled: boolean;
  connected: ConnectionState;
  processing: boolean;
}

export function Composer({ onSubmit, disabled, connected, processing }: ComposerProps) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    setValue('');
  };

  return (
    <div className="composer-wrap">
      <div className={`composer ${disabled ? 'is-disabled' : ''}`}>
        <span className="composer-prefix" aria-hidden>
          ⬡
        </span>
        <textarea
          ref={inputRef}
          className="composer-input"
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={
            connected !== 'connected'
              ? 'Waiting for the Python runtime…'
              : processing
                ? 'HIVE is working…'
                : 'Ask HIVE to run a task…'
          }
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="button"
          className="send-btn"
          disabled={disabled || !value.trim()}
          onClick={submit}
        >
          {processing ? 'Running' : 'Send'}
        </button>
      </div>
      <div className="composer-hint">
        <span>
          {connected === 'connected'
            ? processing
              ? 'Execution in progress'
              : 'Enter to send · Shift+Enter for a new line'
            : 'Runtime offline · restart from the sidebar'}
        </span>
      </div>
    </div>
  );
}
