export interface FriendlyError {
  title: string;
  summary: string;
  detail?: string;
}

export function friendlyChatError(raw: string): FriendlyError {
  const text = (raw || '').trim() || 'Unknown error';

  if (/does not exist or you do not have access|error code:\s*404/i.test(text)) {
    const model = text.match(/model\s+`([^`]+)`/i)?.[1];
    return {
      title: 'Model unavailable',
      summary: model
        ? `${model} isn’t available on this key. Update HIVE_LLM_MODEL in .env, then restart.`
        : 'The configured model isn’t available. Update HIVE_LLM_MODEL in .env, then restart.',
      detail: text,
    };
  }

  if (/tool_calls.*type.*missing|property 'type' is missing/i.test(text)) {
    return {
      title: 'Tool call format error',
      summary: 'The model reply was missing required tool metadata. Restart the runtime and try again.',
      detail: text,
    };
  }

  if (/tool choice is required/i.test(text)) {
    return {
      title: 'Model skipped the tool',
      summary: 'HIVE expected a tool call for this step. Retry the request after restarting the runtime.',
      detail: text,
    };
  }

  if (/missing credentials|openai_api_key|api_key/i.test(text) && /swarm/i.test(text)) {
    return {
      title: 'Swarm unavailable',
      summary: 'Multi-agent mode needs separate credentials. HIVE should continue in single-agent mode.',
      detail: text,
    };
  }

  if (/invalid[_ -]?api[_ -]?key|incorrect api key/i.test(text)) {
    return {
      title: 'API key rejected',
      summary: 'Check HIVE_LLM_API_KEY in .env, then restart the runtime.',
      detail: text,
    };
  }

  if (/error code:\s*413|request too large|TPM:\s*Limit/i.test(text)) {
    return {
      title: 'Model rate limit',
      summary:
        'This request used too many tokens for the free Groq tier. Restart runtime and retry with a shorter ask, or switch models.',
      detail: text,
    };
  }

  if (/error code:\s*400/i.test(text)) {
    return {
      title: 'Request rejected',
      summary: 'The model provider rejected this turn. Restart runtime and try a fresh chat.',
      detail: text,
    };
  }

  const short = text.length > 160 ? `${text.slice(0, 157)}…` : text;
  return {
    title: 'Something went wrong',
    summary: short,
    detail: text.length > 160 ? text : undefined,
  };
}
