"""LLM client — any OpenAI-compatible endpoint.

Defaults to DashScope (Qwen), but HIVE_LLM_BASE_URL / HIVE_LLM_API_KEY /
HIVE_LLM_MODEL retarget it at OpenRouter, Gemini, Groq, OpenCode Zen, or a
local Ollama server without touching code.
"""

import json
import time
from pathlib import Path
from openai import AsyncOpenAI
from hive.config import LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

# #region agent log
_DEBUG_LOG = Path("/Users/bhagatveersingh/PEC HACKATHON/.cursor/debug-8b6d8b.log")

def _dbg(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    try:
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "8b6d8b",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(time.time() * 1000),
                "runId": "pre-fix",
            }, ensure_ascii=False) + "\n")
            f.flush()
    except Exception:
        pass
# #endregion


def _normalize_messages_for_provider(messages: list[dict]) -> list[dict]:
    """Ensure assistant tool_calls include type=function (required by Groq)."""
    out: list[dict] = []
    for msg in messages:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        tool_calls = msg.get("tool_calls")
        if msg.get("role") == "assistant" and tool_calls:
            fixed = []
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    fixed.append(tc)
                    continue
                tc2 = dict(tc)
                tc2["type"] = tc2.get("type") or "function"
                fixed.append(tc2)
            msg = {**msg, "tool_calls": fixed}
        out.append(msg)
    return out


class QwenClient:
    """Async chat client for OpenAI-compatible providers."""

    def __init__(self, api_key: str = LLM_API_KEY,
                 model: str = LLM_MODEL,
                 base_url: str = LLM_BASE_URL):
        self.model = model
        self.base_url = base_url
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def chat(self, messages: list[dict],
                   tools: list[dict] | None = None,
                   tool_choice: str | dict = "auto",
                   temperature: float | None = None,
                   max_tokens: int | None = None) -> dict:
        """Send chat completion request."""
        kwargs = {
            "model": self.model,
            "messages": _normalize_messages_for_provider(messages),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        resp = await self.client.chat.completions.create(**kwargs)
        return resp.model_dump()

    async def stream(self, messages: list[dict],
                     tools: list[dict] | None = None,
                     tool_choice: str | dict = "auto"):
        """Stream chat completion. Yields parsed chunks."""
        kwargs = {
            "model": self.model,
            "messages": _normalize_messages_for_provider(messages),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            # #region agent log
            _dbg("B", "llm.py:stream", "creating stream", {
                "model": self.model,
                "msg_count": len(kwargs.get("messages") or []),
                "tool_count": len(kwargs.get("tools") or []),
                "tools_chars": len(json.dumps(kwargs.get("tools") or [])),
                "msg_chars": sum(len(str(m.get("content") or "")) for m in (kwargs.get("messages") or []) if isinstance(m, dict)),
            })
            # #endregion
            stream = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            # #region agent log
            _dbg("B", "llm.py:stream_error", "provider rejected stream", {
                "model": self.model,
                "error_type": type(e).__name__,
                "error": str(e)[:400],
            })
            # #endregion
            raise
        async for chunk in stream:
            yield chunk.model_dump()

    def extract_response(self, result: dict) -> str:
        """Extract text content from chat response."""
        try:
            return result["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            return ""

    def extract_tool_calls(self, result: dict) -> list[dict]:
        """Extract tool calls from chat response."""
        try:
            return result["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError):
            return []

    def build_tools_schema(self, tools: dict) -> list[dict]:
        """Convert tool registry to OpenAI function calling schema."""
        schema = []
        for name, spec in tools.items():
            # Explicit "required" wins; otherwise preserve the historical
            # first-parameter heuristic for existing tools.
            required_params = list(spec.get("required", []))
            if "required" not in spec:
                for param_name in spec["parameters"]:
                    if param_name in ("query", "path", "command", "url"):
                        required_params.append(param_name)
            properties = {}
            for param_name, param_spec in spec["parameters"].items():
                properties[param_name] = {
                    "type": param_spec["type"],
                    "description": param_spec["description"],
                }

            schema.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required_params,
                    },
                },
            })
        return schema
