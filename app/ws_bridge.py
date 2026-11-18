"""WebSocket RPC Bridge implementing the WebMCP JSON-RPC 2.0 Protocol (/ws/webmcp)."""

from __future__ import annotations

import inspect
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from app.guards import unified_before_tool_callback
from app.store import store
from app.tools import (
    analyze_comment_semiotics,
    competitor_velocity_auditor,
    distribution_strategist,
    generate_sovereign_reply,
    grade_short_package,
    poll_video_comments,
    post_comment_reply,
    publish_video_metadata,
    run_autonomous_pipeline,
    script_architect,
    sentiment_indexer,
    stage_comment_reply,
    sync_youtube_studio_drafts,
    triage_and_grade_comment,
)

logger = logging.getLogger("ayos_den.webmcp")


# Tool function lookup table
TOOL_REGISTRY = {
    "sentiment_indexer": sentiment_indexer,
    "competitor_velocity_auditor": competitor_velocity_auditor,
    "distribution_strategist": distribution_strategist,
    "script_architect": script_architect,
    "run_autonomous_pipeline": run_autonomous_pipeline,
    "analyze_comment_semiotics": analyze_comment_semiotics,
    "generate_sovereign_reply": generate_sovereign_reply,
    "grade_short_package": grade_short_package,
    "triage_and_grade_comment": triage_and_grade_comment,
    "stage_comment_reply": stage_comment_reply,
    "poll_video_comments": poll_video_comments,
    "sync_youtube_studio_drafts": sync_youtube_studio_drafts,
    "publish_video_metadata": publish_video_metadata,
    "post_comment_reply": post_comment_reply,
}


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return WebMCP tool definitions and JSON schemas."""
    definitions = []
    for name, fn in TOOL_REGISTRY.items():
        doc = fn.__doc__ or f"Execute {name}"
        sig = inspect.signature(fn)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif "list" in str(param.annotation).lower() or "List" in str(param.annotation):
                param_type = "array"

            properties[param_name] = {"type": param_type, "description": f"Parameter {param_name}"}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        definitions.append({
            "name": name,
            "description": doc.strip().split("\n")[0],
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        })

    # Include Imperative WebMCP tools registered via navigator.modelContext on frontend
    definitions.extend([
        {
            "name": "poll_reddit_and_velocity",
            "description": "Imperative Frontend Tool: Polls subculture Reddit feeds and triggers velocity checks.",
            "source": "navigator.modelContext",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "subreddit": {"type": "string", "default": "KATSEYE"},
                    "limit": {"type": "integer", "default": 5},
                },
            },
        },
        {
            "name": "query_channel_lore",
            "description": "Imperative Frontend Tool: Queries historical channel lore and prior narrative arcs.",
            "source": "navigator.modelContext",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "arc_id": {"type": "string"},
                },
            },
        },
    ])
    return definitions


class EdgeRateLimiter:
    """Sliding-window edge rate limiter for WebSocket client sessions (max calls per time window)."""

    def __init__(self, max_calls: int = 25, window_seconds: float = 10.0) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._history: Dict[Any, deque[float]] = defaultdict(deque)

    def _get_key(self, client: Any) -> Any:
        return id(client)

    def check_rate_limit(self, client: Any) -> bool:
        """Returns True if request is allowed, False if rate limit is exceeded."""
        key = self._get_key(client)
        now = time.time()
        window_start = now - self.window_seconds
        q = self._history[key]

        while q and q[0] <= window_start:
            q.popleft()

        if len(q) >= self.max_calls:
            return False

        q.append(now)
        return True

    def reset(self, client: Optional[Any] = None) -> None:
        if client is not None:
            self._history.pop(self._get_key(client), None)
        else:
            self._history.clear()


edge_rate_limiter = EdgeRateLimiter(max_calls=25, window_seconds=10.0)


class WebMcpConnectionManager:
    """Manages active WebSocket clients and broadcasts JSON-RPC events."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        # Send initial state snapshot and tool registry
        snapshot = store.get_state_snapshot()
        await websocket.send_json({
            "jsonrpc": "2.0",
            "method": "state/snapshot",
            "params": snapshot,
        })

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        edge_rate_limiter.reset(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        stale = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                stale.add(conn)
        for conn in stale:
            self.active_connections.discard(conn)


manager = WebMcpConnectionManager()


def log_decision_event(
    event_type: str,
    tool_name: str,
    target_id: Any,
    latency_ms: float,
    probabilities: Dict[str, Any],
    confidence: Dict[str, Any],
    passed: bool,
    failing_criteria: Optional[List[str]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Records Decisions API evaluation metrics and broadcasts to WebMCP Inspector."""
    result_data = {
        "target_id": str(target_id),
        "latency_ms": latency_ms,
        "probabilities": probabilities,
        "confidence": confidence,
        "passed": passed,
        "failing_criteria": failing_criteria or [],
        "details": details or {},
    }
    audit_record = store.record_audit_event(
        event_type=f"DECISION_{event_type}",
        tool_name=tool_name,
        arguments={"target_id": str(target_id), "latency_ms": latency_ms},
        result=result_data,
        agent_invoked=True,
        status="PASSED" if passed else "REWRITE_TRIGGERED",
    )
    # Broadcast to active WebMCP WebSocket clients / Inspector stream
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "jsonrpc": "2.0",
            "method": "inspector/decision_event",
            "params": audit_record,
        }))
        loop.create_task(manager.broadcast({
            "jsonrpc": "2.0",
            "method": "audit/event",
            "params": audit_record,
        }))
    except RuntimeError:
        pass
    return audit_record



async def handle_webmcp_message(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Processes inbound JSON-RPC 2.0 WebMCP requests."""
    rpc_id = data.get("id")
    method = data.get("method")
    params = data.get("params") or {}

    try:
        # Edge rate limiting check (sliding window: max 25 calls / 10s per client session)
        if not edge_rate_limiter.check_rate_limit(websocket):
            err_response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32029,
                    "message": "Too Many Requests (429): Rate limit of 25 calls per 10-second window exceeded.",
                    "data": {
                        "status": 429,
                        "retry_after_seconds": 10.0,
                        "max_calls": edge_rate_limiter.max_calls,
                        "window_seconds": edge_rate_limiter.window_seconds,
                    },
                },
            }
            store.record_audit_event(
                event_type="RATE_LIMIT_EXCEEDED",
                tool_name="edge_rate_limiter",
                arguments={"method": method, "id": rpc_id},
                result=err_response["error"],
                status="RATE_LIMITED",
                guard_status="RATE_LIMIT_BLOCKED",
            )
            await websocket.send_json(err_response)
            return

        # 1. Initialize
        if method in ["initialize", "webmcp/initialize"]:
            response = {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2026-06-preview",
                    "serverInfo": {"name": "AyosDenStudioWebMCP", "version": "2.0.0"},
                    "capabilities": {"tools": True, "forms": True, "stateSync": True},
                    "tools": get_tool_definitions(),
                },
            }
            await websocket.send_json(response)
            return

        # 2. Tools List
        if method == "tools/list":
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": get_tool_definitions()},
            })
            return

        # 3. Tools Call
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            agent_invoked = bool(params.get("agentInvoked", False))

            if tool_name not in TOOL_REGISTRY:
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."},
                })
                return

            tool_fn = TOOL_REGISTRY[tool_name]

            # Evaluate deterministic before_tool_callback guardrails
            guard_interception = unified_before_tool_callback(tool_fn, arguments)
            if guard_interception is not None:
                # Guard halted execution!
                audit_record = store.record_audit_event(
                    event_type="GUARD_INTERCEPTED",
                    tool_name=tool_name,
                    arguments=arguments,
                    result=guard_interception,
                    agent_invoked=agent_invoked,
                    status="HALTED_BY_GUARD",
                )
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": guard_interception,
                })
                await manager.broadcast({
                    "jsonrpc": "2.0",
                    "method": "audit/event",
                    "params": audit_record,
                })
                return

            # Execute tool safely
            result = tool_fn(**arguments)
            audit_record = store.record_audit_event(
                event_type="TOOL_CALLED",
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                agent_invoked=agent_invoked,
                status="SUCCESS",
            )

            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": result,
            })

            # Broadcast updated state & audit log
            await manager.broadcast({
                "jsonrpc": "2.0",
                "method": "audit/event",
                "params": audit_record,
            })
            await manager.broadcast({
                "jsonrpc": "2.0",
                "method": "state/snapshot",
                "params": store.get_state_snapshot(),
            })
            return

        # 4. Declarative Forms Submission (<form toolname="..."> with agentInvoked flag)
        if method == "forms/submit":
            toolname = params.get("toolname")
            form_data = params.get("data") or {}
            agent_invoked = bool(params.get("agentInvoked", False))

            if toolname == "stage_video_metadata":
                tags_raw = form_data.get("tags") or []
                if isinstance(tags_raw, str):
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                else:
                    tags = tags_raw

                metadata_payload = {
                    "id": int(form_data.get("id") or 0) or None,
                    "ingestionSource": form_data.get("ingestionSource") or "DeclarativeForm_WebMCP",
                    "rawInput": form_data.get("rawInput") or form_data.get("viral_title") or "",
                    "metadata": {
                        "viral_title": form_data.get("viral_title") or "Untitled Short",
                        "description": form_data.get("description") or "",
                        "tags": tags,
                        "strategy_tier": form_data.get("strategy_tier") or "FEED_FUEL",
                    },
                    "script": {
                        "hookDuration": form_data.get("hookDuration") or "3 seconds",
                        "pacing": form_data.get("pacing") or "High retention pivot",
                    },
                    "status": "Confirmed" if form_data.get("confirm_now") else "Staged",
                }
                saved = store.add_staged_metadata(metadata_payload)
                audit_record = store.record_audit_event(
                    event_type="DECLARATIVE_FORM_SUBMITTED",
                    tool_name=toolname,
                    arguments=form_data,
                    result=saved,
                    agent_invoked=agent_invoked,
                    status="SUCCESS",
                )
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": saved,
                })
                await manager.broadcast({
                    "jsonrpc": "2.0",
                    "method": "audit/event",
                    "params": audit_record,
                })
                await manager.broadcast({
                    "jsonrpc": "2.0",
                    "method": "state/snapshot",
                    "params": store.get_state_snapshot(),
                })
                return

            if toolname == "stage_comment_reply":
                record_id = form_data.get("record_id")
                action = form_data.get("action") or "approve"
                final_reply = form_data.get("final_reply")

                new_status = "APPROVED" if action == "approve" else ("EDITED" if action == "edit" else "SKIPPED")
                store.update_comment_decision(
                    record_id=record_id,
                    status=new_status,
                    final_reply=final_reply,
                    human_verdict=action,
                )
                audit_record = store.record_audit_event(
                    event_type="DECLARATIVE_FORM_SUBMITTED",
                    tool_name=toolname,
                    arguments=form_data,
                    result={"record_id": record_id, "status": new_status},
                    agent_invoked=agent_invoked,
                    status="SUCCESS",
                )
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {"status": "SUCCESS", "record_id": record_id, "new_status": new_status},
                })
                await manager.broadcast({
                    "jsonrpc": "2.0",
                    "method": "audit/event",
                    "params": audit_record,
                })
                await manager.broadcast({
                    "jsonrpc": "2.0",
                    "method": "state/snapshot",
                    "params": store.get_state_snapshot(),
                })
                return

            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32602, "message": f"Unsupported form toolname: {toolname}"},
            })
            return

        # 5. State Get
        if method == "state/get":
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": store.get_state_snapshot(),
            })
            return

        # 6. Metadata Confirmation
        if method == "confirm/metadata":
            item_id = int(params.get("id"))
            success = store.confirm_metadata(item_id)
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"id": item_id, "confirmed": success},
            })
            await manager.broadcast({
                "jsonrpc": "2.0",
                "method": "state/snapshot",
                "params": store.get_state_snapshot(),
            })
            return

        # Method not found
        await websocket.send_json({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."},
        })

    except Exception as e:
        logger.error(f"Error handling WebMCP RPC: {e}", exc_info=True)
        if rpc_id is not None:
            await websocket.send_json({
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32000, "message": str(e)},
            })
