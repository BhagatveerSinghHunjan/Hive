"""Runtime — agent execution loop with process isolation."""

# #region agent log
import json as _dbg_json
import time as _dbg_time
from pathlib import Path as _DbgPath
_DEBUG_LOG = _DbgPath("/Users/bhagatveersingh/PEC HACKATHON/.cursor/debug-8b6d8b.log")

def _dbg(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    try:
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(_dbg_json.dumps({
                "sessionId": "8b6d8b",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(_dbg_time.time() * 1000),
                "runId": "pre-fix",
            }, ensure_ascii=False) + "\n")
            f.flush()
    except Exception:
        pass
# #endregion

import asyncio
import json
import time
import types
from concurrent.futures import ProcessPoolExecutor
from hive.config import MAX_AGENTS, AGENT_TIMEOUT, MAX_ITERATIONS
from hive.llm import QwenClient
from hive.tools import TOOLS, execute_tool, select_tools_for_llm
from hive.permissions import get_tool_tier, check_dangerous_command, should_auto_allow
from hive.agents.safety_agent import SafetyAgent
from hive.core.agent_state import get_or_create_state


def _run_agent_process(agent_code: str, task: str, context: dict) -> dict:
    """Runs in a separate process. Agent's own memory space."""
    module = types.ModuleType("agent_module")
    module.__dict__["__name__"] = "agent_module"
    try:
        exec(agent_code, module.__dict__)
    except Exception as e:
        return {"error": f"Agent code execution failed: {e}"}

    agent_class = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "execute"):
            agent_class = obj
            break

    if not agent_class:
        return {"error": "No agent class with execute() method found"}

    try:
        agent = agent_class()
        result = agent.execute(task, context)
        return {"result": result}
    except Exception as e:
        return {"error": f"Agent execution failed: {e}"}


MAX_LOOP_ITERATIONS = MAX_ITERATIONS


def format_approval_target(tool_name: str, args: dict) -> str:
    """Human-readable target for approval prompts (recipient, event, amount)."""
    args = args or {}

    def first(*keys):
        for key in keys:
            value = args.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    if tool_name.startswith("gmail_"):
        to = first("to", "draft_id", "thread_id", "message_id")
        subject = first("subject")
        if subject and to:
            return f"{to} — {subject}"
        return subject or to

    if tool_name.startswith("calendar_"):
        summary = first("summary", "event_id")
        when = first("start", "range_start", "time_min")
        if summary and when:
            return f"{summary} @ {when}"
        return summary or when

    if tool_name.startswith("task"):
        return first("title", "task_id")

    if tool_name == "browser_checkout":
        merchant = first("merchant", "store")
        amount = first("amount", "total")
        if merchant or amount:
            return f"{merchant} — {amount}".strip(" —")

    if tool_name.startswith("browser_playbook") or tool_name.startswith("browser_record"):
        site = first("site", "url", "domain")
        flow = first("flow", "name")
        if site and flow:
            return f"{site} / {flow}"
        return site or flow

    return first("path", "url", "site", "command", "query", "target")


def humanize_tool_result(tool_name: str, result: object) -> str | None:
    """Turn structured tool payloads into a short user-facing sentence."""
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return str(result["error"])
    if isinstance(result.get("message"), str) and result.get("message").strip():
        # Prefer an explicit message when the tool already wrote one.
        if tool_name == "spotify_control" or result.get("action") or result.get("playing"):
            pass  # fall through to richer Spotify wording when possible
        elif result.get("ok") is True or "ok" not in result:
            return result["message"].strip()

    action = str(result.get("action") or "").lower()
    playing = result.get("playing")
    if tool_name == "spotify_control" or action in {
        "play",
        "pause",
        "resume",
        "next",
        "previous",
        "now_playing",
    } or isinstance(playing, dict):
        device = ""
        if isinstance(result.get("device"), dict):
            device = str(result["device"].get("name") or "").strip()
        elif isinstance(result.get("device"), str):
            device = result["device"].strip()
        where = f" on {device}" if device else ""

        if isinstance(playing, dict) and playing.get("name"):
            track = str(playing.get("name") or "").strip()
            artists = str(playing.get("artists") or "").strip()
            who = f" by {artists}" if artists else ""
            if action in ("play", "search_play", "start", "play_playlist", ""):
                return f"Playing {track}{who}{where}."
            return f"Now playing {track}{who}{where}."

        name = str(result.get("name") or "").strip()
        artists = str(result.get("artists") or "").strip()
        if name:
            who = f" by {artists}" if artists else ""
            if result.get("playing") is False:
                return f"Paused — was {name}{who}{where}."
            return f"{'Playing' if result.get('playing') else 'On Spotify'}: {name}{who}{where}."

        if action == "pause":
            return f"Paused Spotify{where}."
        if action in ("resume", "unpause"):
            return f"Resumed Spotify{where}."
        if action in ("next", "skip"):
            return f"Skipped to the next track{where}."
        if action in ("previous", "prev"):
            return f"Went back to the previous track{where}."
        if result.get("ok"):
            return f"Spotify {action or 'ok'}{where}."

    if tool_name in ("web_search", "exa_search") or result.get("results") or result.get("answers"):
        results = result.get("results") or result.get("answers") or []
        if isinstance(results, list) and results:
            first = results[0] if isinstance(results[0], dict) else {}
            title = first.get("title") or first.get("url") or "results"
            return f"Found {len(results)} result(s). Top: {title}."

    if result.get("ok") is True and isinstance(result.get("message"), str):
        return result["message"].strip()
    return None


def _strip_code_fence(text: str) -> str:
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    lines = raw.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def finalize_assistant_text(text: str, fallbacks: list[str] | None = None) -> str:
    """Replace raw tool-JSON dumps with a normal spoken reply."""
    fallbacks = fallbacks or []
    raw = (text or "").strip()
    if not raw:
        return fallbacks[-1] if fallbacks else "Done."

    candidate = _strip_code_fence(raw)
    if candidate.startswith("{") and candidate.endswith("}"):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            spoken = humanize_tool_result("", data)
            if spoken:
                return spoken
            if fallbacks:
                return fallbacks[-1]

    # Model sometimes prefixes a short line then dumps JSON
    if "\n{" in candidate and candidate.rstrip().endswith("}"):
        maybe_json = candidate[candidate.find("{") :].strip()
        try:
            data = json.loads(maybe_json)
            spoken = humanize_tool_result("", data) if isinstance(data, dict) else None
            if spoken:
                prefix = candidate[: candidate.find("{")].strip()
                return f"{prefix}\n{spoken}" if prefix and len(prefix) < 120 else spoken
        except json.JSONDecodeError:
            pass

    return text if text else (fallbacks[-1] if fallbacks else "Done.")


def _tool_message_content(tool_name: str, result: object) -> str:
    payload = json.dumps(result)
    summary = humanize_tool_result(tool_name, result)
    if not summary:
        return payload
    return (
        f"{payload}\n\n"
        f"[Reply to the user in plain language using this summary — never paste raw JSON]: {summary}"
    )


class AgentRuntime:
    """Manages agent execution with process isolation."""

    def __init__(self, llm: QwenClient):
        self.llm = llm
        self.executor = None
        self.active = {}

    async def run_agent(self, agent_code: str, task: str,
                        context: dict) -> dict:
        """Run agent in separate process."""
        if self.executor is None:
            self.executor = ProcessPoolExecutor(max_workers=MAX_AGENTS)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.executor,
            _run_agent_process,
            agent_code,
            task,
            json.dumps(context),
        )
        try:
            result = await asyncio.wait_for(future, timeout=AGENT_TIMEOUT)
            return result
        except asyncio.TimeoutError:
            return {"error": f"Agent timed out after {AGENT_TIMEOUT}s"}

    async def run_loop(self, session_id: str, messages: list[dict],
                       on_tool_call=None, on_permission=None, on_text=None) -> str:
        """Main agent loop: send to LLM, execute tools, repeat. Uses streaming for fast token display."""
        # Merge MCP tools into TOOLS registry
        try:
            from hive.mcp.bridge import mcp_bridge
            mcp_tools = mcp_bridge.get_hive_tools()
            if mcp_tools:
                from hive.tools import register_mcp_tools
                register_mcp_tools(mcp_tools)
        except ImportError:
            pass

        last_user = ""
        for msg in reversed(messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                last_user = str(msg.get("content") or "")
                break
        active_tools = select_tools_for_llm(TOOLS, user_message=last_user)
        tools_schema = self.llm.build_tools_schema(active_tools)
        conversation = list(messages)
        iteration = 0
        agent_state = get_or_create_state("single_agent")
        agent_state.task_started()

        # #region agent log
        _tools_chars = len(json.dumps(tools_schema))
        _msg_chars = sum(len(str(m.get("content") or "")) for m in conversation)
        _dbg("B", "runtime.py:run_loop", "request budget estimate", {
            "tool_count": len(tools_schema),
            "registry_tools": len(TOOLS),
            "active_tools": len(active_tools),
            "tools_chars": _tools_chars,
            "tools_est_tokens": _tools_chars // 4,
            "msg_count": len(conversation),
            "msg_chars": _msg_chars,
            "msg_est_tokens": _msg_chars // 4,
            "total_est_tokens": (_tools_chars + _msg_chars) // 4,
            "model": getattr(self.llm, "model", None),
            "runId_tag": "post-fix",
        })
        # #endregion

        try:
            # Use auto so simple chat (e.g. "hi") works on Groq/OSS models that
            # reject forced tool_choice="required" when no tool is needed.
            current_tool_choice = "auto"
            last_tool_summaries: list[str] = []

            while iteration < MAX_LOOP_ITERATIONS:
                iteration += 1
                
                # Use streaming for fast token-by-token display
                full_content = ""
                tool_calls = []
                
                try:
                    _stream_iter = self.llm.stream(conversation, tools=tools_schema, tool_choice=current_tool_choice)
                except Exception as stream_init_err:
                    # #region agent log
                    _dbg("B", "runtime.py:stream_init", "stream init failed", {
                        "iteration": iteration,
                        "error": str(stream_init_err)[:300],
                    })
                    # #endregion
                    raise

                async for chunk in _stream_iter:
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    
                    # Stream content token by token
                    if delta.get("content"):
                        token = delta["content"]
                        full_content += token
                        if on_text:
                            await on_text(token)
                    
                    # Collect tool calls
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            while len(tool_calls) <= idx:
                                tool_calls.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )
                            tool_calls[idx]["type"] = "function"
                            if tc.get("id"):
                                tool_calls[idx]["id"] = tc["id"]
                            if tc.get("type"):
                                tool_calls[idx]["type"] = tc["type"]
                            if tc.get("function", {}).get("name"):
                                tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                import logging
                _log = logging.getLogger("hive.runtime")
                _log.warning(f"[RUNTIME] Iteration {iteration}: content_len={len(full_content)}, tool_calls={len(tool_calls)}")
                if tool_calls:
                    for tc in tool_calls:
                        _log.warning(f"[RUNTIME] Tool: {tc['function']['name']}({tc['function']['arguments'][:200]})")

                if not tool_calls:
                    agent_state.task_completed(success=True)
                    return finalize_assistant_text(
                        full_content or "",
                        last_tool_summaries,
                    )

                # After first tool call, switch to auto so model can respond with text
                current_tool_choice = "auto"

                # Groq/OpenAI require tool_calls[].type == "function"
                for tc in tool_calls:
                    tc["type"] = tc.get("type") or "function"

                # When tool_calls present, content should be empty to avoid API issues
                assistant_msg = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                conversation.append(assistant_msg)

                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}

                    tier = get_tool_tier(tool_name)
                    target = format_approval_target(tool_name, args)

                    if tier == "dangerous":
                        decision = "denied"
                        if on_permission:
                            decision = await on_permission(tool_name, target, tier)
                        if decision != "approved":
                            tool_result = {"error": f"Denied: {tool_name}"}
                            conversation.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": json.dumps(tool_result),
                            })
                            continue

                    if tier in ("moderate", "sensitive"):
                        if not should_auto_allow(tool_name, target):
                            decision = "denied"
                            if on_permission:
                                decision = await on_permission(tool_name, target, tier)
                            if decision != "approved":
                                tool_result = {"error": f"Denied: {tool_name}"}
                                conversation.append({
                                    "role": "tool",
                                    "tool_call_id": tc.get("id", ""),
                                    "content": json.dumps(tool_result),
                                })
                                continue

                    if tool_name == "run_command" and args.get("command"):
                        if check_dangerous_command(args["command"]):
                            tool_result = {"error": f"Blocked dangerous command pattern: {args['command'][:100]}"}
                            conversation.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": json.dumps(tool_result),
                            })
                            continue

                    safety = SafetyAgent(task_context=str(args))
                    safety_check = await safety.check(str(args))
                    if not safety_check.get("approved", True):
                        tool_result = {"error": f"SafetyAgent blocked: {safety_check.get('reason')}"}
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": json.dumps(tool_result),
                        })
                        continue

                    if on_tool_call:
                        await on_tool_call(tool_name, args)

                    result = await execute_tool(tool_name, **args)
                    _log.warning(f"[RUNTIME] Tool {tool_name} result: {str(result)[:300]}")
                    spoken = humanize_tool_result(tool_name, result)
                    if spoken:
                        last_tool_summaries.append(spoken)

                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": _tool_message_content(tool_name, result),
                    })

            agent_state.task_completed(success=False)
            return finalize_assistant_text(
                full_content or "",
                last_tool_summaries,
            ) or (
                f"I reached the maximum number of tool iterations ({MAX_LOOP_ITERATIONS})."
            )
        except Exception as e:
            # #region agent log
            _dbg("B", "runtime.py:run_loop_error", "run_loop failed", {
                "error_type": type(e).__name__,
                "error": str(e)[:400],
                "is_413": "413" in str(e) or "too large" in str(e).lower() or "TPM" in str(e),
            })
            # #endregion
            agent_state.task_completed(success=False)
            raise

    async def run_loop_streaming(self, session_id: str, messages: list[dict],
                                  live=None, dash=None) -> str:
        """Agent loop with streaming output - tokens appear line by line."""
        # Merge MCP tools into TOOLS registry
        try:
            from hive.mcp.bridge import mcp_bridge
            mcp_tools = mcp_bridge.get_hive_tools()
            if mcp_tools:
                from hive.tools import register_mcp_tools
                register_mcp_tools(mcp_tools)
        except ImportError:
            pass

        last_user = ""
        for msg in reversed(messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                last_user = str(msg.get("content") or "")
                break
        active_tools = select_tools_for_llm(TOOLS, user_message=last_user)
        tools_schema = self.llm.build_tools_schema(active_tools)
        conversation = list(messages)
        iteration = 0
        agent_state = get_or_create_state("single_agent")
        agent_state.task_started()
        
        # For streaming output
        collected_content = []
        current_response = []
        
        try:
            # Use auto so providers like Groq gpt-oss can answer without tools.
            current_tool_choice = "auto"
            last_tool_summaries: list[str] = []

            while iteration < MAX_LOOP_ITERATIONS:
                iteration += 1
                
                # Use streaming
                full_content = ""
                tool_calls = []
                
                async for chunk in self.llm.stream(conversation, tools=tools_schema, tool_choice=current_tool_choice):
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    
                    # Stream content token by token
                    if delta.get("content"):
                        token = delta["content"]
                        full_content += token
                        current_response.append(token)
                        
                        # Print token immediately (line by line effect)
                        import sys
                        sys.stdout.write(token)
                        sys.stdout.flush()
                        
                        # Update dashboard
                        if dash:
                            dash.set_status("thinking")
                
                if not full_content and not tool_calls:
                    # Check for tool calls in final message
                    result = await self.llm.chat(conversation, tools=tools_schema)
                    message = result.get("choices", [{}])[0].get("message") or {}
                    full_content = message.get("content") or ""
                    tool_calls = message.get("tool_calls") or []
                
                if not tool_calls:
                    agent_state.task_completed(success=True)
                    return finalize_assistant_text(
                        full_content or "",
                        last_tool_summaries,
                    )

                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tc["type"] = tc.get("type") or "function"
                
                # Handle tool calls
                assistant_msg = {"role": "assistant", "content": full_content, "tool_calls": tool_calls}
                conversation.append(assistant_msg)
                
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}
                    
                    tier = get_tool_tier(tool_name)
                    target = format_approval_target(tool_name, args)
                    
                    if tier == "dangerous":
                        tool_result = {"error": f"Denied: {tool_name}"}
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": _tool_message_content(tool_name, tool_result),
                        })
                        continue
                    
                    if tool_name == "run_command" and args.get("command"):
                        if check_dangerous_command(args["command"]):
                            tool_result = {"error": f"Blocked dangerous command: {args['command'][:100]}"}
                            conversation.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": _tool_message_content(tool_name, tool_result),
                            })
                            continue
                    
                    # Update dashboard with tool execution
                    if dash:
                        dash.set_status(f"running {tool_name}")
                    
                    # Print tool execution
                    import sys
                    sys.stdout.write(f"\n  [tool] {tool_name}")
                    sys.stdout.flush()
                    
                    result = await execute_tool(tool_name, **args)
                    spoken = humanize_tool_result(tool_name, result)
                    if spoken:
                        last_tool_summaries.append(spoken)
                    
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": _tool_message_content(tool_name, result),
                    })
                
                # After first tool call, switch to auto so model can respond with text
                current_tool_choice = "auto"
            
            agent_state.task_completed(success=False)
            return finalize_assistant_text(
                full_content or "",
                last_tool_summaries,
            ) or "Max iterations reached."
        except Exception as e:
            agent_state.task_completed(success=False)
            raise

    def shutdown(self):
        """Shutdown process pool."""
        if self.executor:
            self.executor.shutdown(wait=False)
