"""Interactive chat API — a Claude Code session in a browser window.

This is the backend half of the in-app chat ("talk to Claude Code directly").
It runs the **Claude Agent SDK**, which drives the local ``claude`` CLI on
David's Max subscription (same inference path as the one-shot skills in
``modules/agents/claude_cli.py``, but here it's a *persistent, streaming,
multi-turn* session instead of a single ``claude -p`` call).

Phase B (this file): the agent can read **and act**, but every write / command /
skill-run is gated by a **per-action approval** that pops in the chat UI — David
approves or declines each one. Two safety rails:

* **Vault writes never use the built-in editor.** The CLAUDE.md rule (OneDrive
  sync corrupts files edited via Edit/Write) is enforced here: built-in
  Edit/Write/MultiEdit/NotebookEdit aimed at a vault path are *denied* and the
  agent is redirected to the in-process :func:`vault_write` tool, which routes
  through :func:`core.vault.write_md` (Python I/O + ``.bak`` backup).
* Reads/searches are auto-approved; everything else asks first.

Protocol — a JSON WebSocket at ``/api/chat/stream`` (optionally
``?page=/money&resume=<session_id>``):

    client -> server   {"type": "user", "text": "..."}
                       {"type": "approve", "request_id": "..."}
                       {"type": "deny", "request_id": "...", "message": "..."}

    server -> client   {"type": "session", "session_id": "..."}
                       {"type": "text_delta", "text": "..."}
                       {"type": "thinking_delta", "text": "..."}
                       {"type": "tool_use", "id", "name", "input"}
                       {"type": "approval_request", "request_id", "name", "input", "tool_use_id"}
                       {"type": "tool_result", "tool_use_id", "content", "is_error"}
                       {"type": "result", "session_id", "cost", "duration_ms", "is_error"}
                       {"type": "error", "message": "..."}
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    CLINotFoundError,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    tool,
)

from core.config import REPO_ROOT, VAULT_PATH, get_logger
from core.vault import read_md, write_md

logger = get_logger(__name__)
router = APIRouter()

Sender = Callable[[dict[str, Any]], Awaitable[None]]

# Auto-approved (no prompt). Everything else routes through the approval flow.
READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "WebSearch", "WebFetch", "TodoWrite"]
# Built-in file editors — denied on vault paths (must use vault_write instead).
BUILTIN_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _is_vault_path(raw: str | None) -> bool:
    """True if ``raw`` resolves to a path inside David's OneDrive vault."""
    if not raw:
        return False
    try:
        target = Path(raw)
        if not target.is_absolute():
            target = VAULT_PATH / raw
        target = target.resolve()
        vault = VAULT_PATH.resolve()
        return target == vault or vault in target.parents
    except (OSError, ValueError):
        return False


def _resolve_vault(raw: str) -> Path | None:
    """Resolve a (possibly relative) path under the vault, or None if it escapes."""
    p = Path(raw)
    if not p.is_absolute():
        p = VAULT_PATH / raw
    return p if _is_vault_path(str(p)) else None


# --- In-process MCP tools (vault-safe writes + skill launcher) ---------------
@tool(
    "vault_write",
    "Overwrite a file in David's Obsidian vault SAFELY (Python I/O, saves a .bak "
    "backup first). Use this for ANY vault file — never the built-in Edit/Write, "
    "which corrupts OneDrive-synced files. `path` may be vault-relative or absolute.",
    {"path": str, "content": str},
)
async def vault_write(args: dict[str, Any]) -> dict[str, Any]:
    p = _resolve_vault(str(args.get("path", "")))
    if p is None:
        return {"content": [{"type": "text", "text": f"Refused: '{args.get('path')}' is not inside the vault."}], "is_error": True}
    content = str(args.get("content", ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    write_md(p, content)
    return {"content": [{"type": "text", "text": f"Wrote {p} ({len(content)} chars; .bak saved if it existed)."}]}


@tool(
    "vault_append",
    "Append text to a vault file SAFELY (Python I/O, .bak backup). Creates the "
    "file if missing. `path` may be vault-relative or absolute.",
    {"path": str, "content": str},
)
async def vault_append(args: dict[str, Any]) -> dict[str, Any]:
    p = _resolve_vault(str(args.get("path", "")))
    if p is None:
        return {"content": [{"type": "text", "text": f"Refused: '{args.get('path')}' is not inside the vault."}], "is_error": True}
    addition = str(args.get("content", ""))
    existing = read_md(p)
    sep = "" if (not existing or existing.endswith("\n")) else "\n"
    write_md(p, existing + sep + addition)
    return {"content": [{"type": "text", "text": f"Appended {len(addition)} chars to {p} (.bak saved)."}]}


@tool(
    "run_skill",
    "Launch one of David's registered background skills (long claude -p analyses). "
    "Returns a run_id; results stream to the Background Runs page. `args_json` is a "
    "JSON object string of the skill's arguments.",
    {"name": str, "args_json": str},
)
async def run_skill(args: dict[str, Any]) -> dict[str, Any]:
    from backend.api.skills import SKILL_REGISTRY, _REQUIRED
    from modules.agents import background

    name = str(args.get("name", ""))
    if name not in SKILL_REGISTRY:
        return {
            "content": [{"type": "text", "text": "Unknown skill. Available: " + ", ".join(sorted(SKILL_REGISTRY))}],
            "is_error": True,
        }
    module_path, callable_name, params = SKILL_REGISTRY[name]
    raw = str(args.get("args_json") or "").strip()
    try:
        supplied = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        return {"content": [{"type": "text", "text": f"args_json is not valid JSON: {exc}"}], "is_error": True}

    positional: list[Any] = []
    for param_name, default in params:
        if param_name in supplied:
            positional.append(supplied[param_name])
        elif default is _REQUIRED:
            return {"content": [{"type": "text", "text": f"Missing required arg '{param_name}' for skill '{name}'."}], "is_error": True}
        else:
            positional.append(default)

    info = background.launch(module_path=module_path, callable_name=callable_name, args=positional, label=name)
    return {"content": [{"type": "text", "text": f"Launched '{name}' (run_id={info['run_id']}). Track it on the Background Runs page."}]}


def _system_append(page: str | None) -> str:
    where = f"\nDavid opened this chat from the dashboard page: `{page}`." if page else ""
    return f"""
You are the assistant embedded in David's **Personal Command Center** — a local
FastAPI + React dashboard that reads his Obsidian vault. You are talking to him
directly inside a chat window in that app, exactly like talking to Claude Code.

- This repository (your working directory) is: {REPO_ROOT}
- David's Obsidian vault is at: {VAULT_PATH}
  Useful vault files: 99_System/Personal_Memory.md, 99_System/Project_Index.md,
  99_System/Task_Command_Center.md, 99_System/Command_Center_Architecture.md.
- Read the project's CLAUDE.md for the code + vault I/O rules.{where}

CAPABILITIES: you can read freely; writes, shell commands and skill-runs each
require David's one-click approval (a card appears in the chat). Specifically:
- Repo code under {REPO_ROOT}: use the normal Edit/Write tools (he'll approve).
- VAULT files under {VAULT_PATH}: you MUST use the `vault_write` / `vault_append`
  tools — NEVER the built-in Edit/Write (they corrupt OneDrive-synced files).
  Those built-ins are blocked on vault paths.
- To run a heavy analysis, use `run_skill` (it launches a background run).

Honour the global rule in CLAUDE.md: if a task needs David's original creative
thinking (his voice/principles/strategy), tell him to think in Miro/OneNote
first rather than producing it for him. Be concise; answer in Markdown.
""".strip()


async def _stream_turn(client: ClaudeSDKClient, send: Sender) -> None:
    """Translate one assistant turn from the SDK into WebSocket frames."""
    async for message in client.receive_response():
        if isinstance(message, StreamEvent):
            event = message.event or {}
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                dtype = delta.get("type")
                if dtype == "text_delta":
                    await send({"type": "text_delta", "text": delta.get("text", "")})
                elif dtype == "thinking_delta":
                    await send({"type": "thinking_delta", "text": delta.get("thinking", "")})

        elif isinstance(message, SystemMessage):
            if message.subtype == "init":
                sid = (message.data or {}).get("session_id")
                if sid:
                    await send({"type": "session", "session_id": sid})

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    await send({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})

        elif isinstance(message, UserMessage):
            content = message.content if isinstance(message.content, list) else []
            for block in content:
                if isinstance(block, ToolResultBlock):
                    await send(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": _stringify_tool_result(block.content),
                            "is_error": bool(block.is_error),
                        }
                    )

        elif isinstance(message, ResultMessage):
            await send(
                {
                    "type": "result",
                    "session_id": message.session_id,
                    "cost": message.total_cost_usd,
                    "duration_ms": message.duration_ms,
                    "is_error": message.is_error,
                }
            )


def _stringify_tool_result(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            parts.append(str(item.get("text", item)) if isinstance(item, dict) else str(item))
        return "\n".join(parts)
    return "" if content is None else str(content)


@router.websocket("/stream")
async def chat_stream(
    websocket: WebSocket,
    page: str | None = Query(None),
    resume: str | None = Query(None),
) -> None:
    """A persistent, streaming, multi-turn Claude Code chat with per-action approval.

    A dedicated reader task drains the socket so we can receive an approval reply
    *while* a turn is still streaming (the ``can_use_tool`` callback fires inside
    the SDK's stream and awaits David's decision). All outbound frames go through
    a lock since the streamer and the approval callback both send concurrently.
    """
    await websocket.accept()

    send_lock = asyncio.Lock()

    async def send(frame: dict[str, Any]) -> None:
        async with send_lock:
            await websocket.send_json(frame)

    pending: dict[str, asyncio.Future] = {}
    user_queue: asyncio.Queue = asyncio.Queue()
    counter = {"n": 0}

    async def can_use_tool(tool_name: str, input_data: dict[str, Any], context: ToolPermissionContext):
        # Vault guard: built-in editors are never allowed on vault paths.
        if tool_name in BUILTIN_EDIT_TOOLS:
            target = input_data.get("file_path") or input_data.get("notebook_path") or ""
            if _is_vault_path(target):
                return PermissionResultDeny(
                    message=(
                        "That path is inside David's OneDrive vault. Use the `vault_write` "
                        "or `vault_append` tool instead — the built-in editor can corrupt "
                        "OneDrive-synced files."
                    )
                )
        # Ask David to approve everything else (writes / bash / skills / mcp).
        counter["n"] += 1
        rid = f"r{counter['n']}"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        pending[rid] = fut
        await send(
            {
                "type": "approval_request",
                "request_id": rid,
                "name": tool_name,
                "input": input_data,
                "tool_use_id": getattr(context, "tool_use_id", None),
            }
        )
        try:
            resp = await fut
        except asyncio.CancelledError:
            return PermissionResultDeny(message="Disconnected before approval.")
        finally:
            pending.pop(rid, None)
        if resp.get("type") == "approve":
            return PermissionResultAllow()
        return PermissionResultDeny(message=resp.get("message") or "David declined this action.")

    async def reader() -> None:
        """Drain the socket: queue user turns, resolve approval futures."""
        try:
            while True:
                raw = await websocket.receive_json()
                if not isinstance(raw, dict):
                    continue
                t = raw.get("type")
                if t == "user":
                    await user_queue.put(raw)
                elif t in ("approve", "deny"):
                    fut = pending.get(raw.get("request_id", ""))
                    if fut and not fut.done():
                        fut.set_result(raw)
                # pings / unknown frames ignored
        except WebSocketDisconnect:
            await user_queue.put(None)
            for fut in list(pending.values()):
                if not fut.done():
                    fut.cancel()

    cc_server = create_sdk_mcp_server("cc", tools=[vault_write, vault_append, run_skill])

    options = ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": _system_append(page)},
        cwd=str(REPO_ROOT),
        add_dirs=[str(VAULT_PATH)],
        allowed_tools=READ_ONLY_TOOLS,
        mcp_servers={"cc": cc_server},
        can_use_tool=can_use_tool,
        permission_mode="default",
        # Load NO filesystem settings: David's ~/.claude + project allowlists were
        # written for the interactive CLI and would silently pre-approve tools,
        # bypassing this chat's approval gate. With [] our can_use_tool is the sole
        # authority, so every write/command/skill genuinely asks first. (The vault
        # rules CLAUDE.md would supply are already injected via _system_append.)
        setting_sources=[],
        include_partial_messages=True,
        resume=resume or None,
    )

    reader_task: asyncio.Task | None = None
    try:
        async with ClaudeSDKClient(options=options) as client:
            reader_task = asyncio.create_task(reader())
            while True:
                item = await user_queue.get()
                if item is None:  # disconnected
                    break
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                try:
                    await client.query(text)
                    await _stream_turn(client, send)
                except Exception as exc:  # one bad turn shouldn't kill the socket
                    logger.exception("chat: turn failed")
                    await send({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    except CLINotFoundError:
        logger.exception("chat: claude CLI not found")
        await _safe_send(websocket, {"type": "error", "message": "`claude` CLI not found — is Claude Code installed and on PATH?"})
    except Exception as exc:
        logger.exception("chat: session failed")
        await _safe_send(websocket, {"type": "error", "message": str(exc)})
    finally:
        if reader_task is not None:
            reader_task.cancel()


async def _safe_send(websocket: WebSocket, frame: dict[str, Any]) -> None:
    try:
        await websocket.send_json(frame)
    except Exception:
        pass
