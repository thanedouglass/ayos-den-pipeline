"""WebMcpStore: Thread-safe SQLite State Mirror and queue.json Synchronizer."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import config


class WebMcpStore:
    """Server-side state mirror managing live session state, drafts, queue, and WebMCP audit logs."""

    def __init__(self, db_path: Optional[Path | str] = None, queue_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path or config.db_path)
        self.queue_path = Path(queue_path or config.queue_json_path)
        self._init_db()
        self._hydrate_from_queue_json_if_needed()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS staged_metadata (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    ingestion_source TEXT NOT NULL,
                    raw_input TEXT NOT NULL,
                    viral_title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    strategy_tier TEXT NOT NULL,
                    hook_duration TEXT,
                    pacing TEXT,
                    status TEXT NOT NULL DEFAULT 'Staged',
                    confirmation_token TEXT,
                    agent_results TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS staged_comments (
                    id TEXT PRIMARY KEY,
                    comment_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    video_title TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    input_comment TEXT NOT NULL,
                    category TEXT NOT NULL,
                    semiotic_intent TEXT NOT NULL,
                    energy_level INTEGER NOT NULL DEFAULT 3,
                    model_draft_reply TEXT NOT NULL,
                    final_reply TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
                    human_verdict TEXT,
                    alignment_delta REAL,
                    confirmation_token TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL,
                    result TEXT,
                    agent_invoked INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'SUCCESS',
                    sanitization_flags TEXT,
                    guard_status TEXT
                );
                """
            )
            # Safe schema migration for existing SQLite files
            cursor = conn.execute("PRAGMA table_info(audit_events);")
            cols = {row["name"] for row in cursor.fetchall()}
            if "sanitization_flags" not in cols:
                conn.execute("ALTER TABLE audit_events ADD COLUMN sanitization_flags TEXT;")
            if "guard_status" not in cols:
                conn.execute("ALTER TABLE audit_events ADD COLUMN guard_status TEXT;")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_staged_metadata_status ON staged_metadata (status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_staged_comments_status ON staged_comments (status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events (timestamp);")
            conn.commit()

    def _hydrate_from_queue_json_if_needed(self) -> None:
        """Seed SQLite store from existing queue.json if database is currently empty."""
        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM staged_metadata;").fetchone()[0]
            if count == 0 and self.queue_path.exists():
                try:
                    data = json.loads(self.queue_path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for item in data:
                            meta = item.get("metadata") or {}
                            agent_res = item.get("agentResults") or {}
                            tags = meta.get("tags") or meta.get("backendTags") or []
                            if isinstance(tags, str):
                                tags = [t.strip() for t in tags.split(",") if t.strip()]

                            conn.execute(
                                """
                                INSERT OR REPLACE INTO staged_metadata (
                                    id, timestamp, ingestion_source, raw_input, viral_title,
                                    description, tags, strategy_tier, hook_duration, pacing,
                                    status, agent_results
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                                """,
                                (
                                    item.get("id") or int(time.time() * 1000),
                                    item.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                                    item.get("ingestionSource") or item.get("route") or "manual",
                                    item.get("rawInput") or "",
                                    meta.get("title") or meta.get("viral_title") or "Untitled Short",
                                    meta.get("description") or "",
                                    json.dumps(tags),
                                    meta.get("strategy_tier") or "FEED_FUEL",
                                    agent_res.get("script", {}).get("hookDuration") or "3 seconds",
                                    agent_res.get("script", {}).get("pacing") or "Fast pivot",
                                    item.get("status") or "Staged",
                                    json.dumps(agent_res),
                                ),
                            )
                        conn.commit()
                except Exception as e:
                    print(f"Warning: Failed to hydrate store from queue.json: {e}")

    # --------------------------------------------------------------------------
    # Video Metadata Queue Operations
    # --------------------------------------------------------------------------

    def add_staged_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update video metadata entry and dual-write to queue.json."""
        item_id = payload.get("id") or int(time.time() * 1000)
        ts = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
        source = payload.get("ingestionSource") or payload.get("source") or "autonomous_agent"
        raw_text = payload.get("rawInput") or payload.get("raw_text") or ""

        agent_results = payload.get("agentResults") or {}
        metadata = payload.get("metadata") or agent_results.get("metadata") or {}
        script = payload.get("script") or agent_results.get("script") or {}

        viral_title = metadata.get("viral_title") or metadata.get("title") or "Untitled Short Hook"
        description = metadata.get("description") or ""
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        strategy_tier = metadata.get("strategy_tier") or "FEED_FUEL"

        hook_dur = script.get("hookDuration") or "3 seconds"
        pacing = script.get("pacing") or "High retention pivot"
        status = payload.get("status") or "Staged"
        token = payload.get("confirmation_token") or str(uuid.uuid4())

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO staged_metadata (
                    id, timestamp, ingestion_source, raw_input, viral_title,
                    description, tags, strategy_tier, hook_duration, pacing,
                    status, confirmation_token, agent_results
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item_id,
                    ts,
                    source,
                    raw_text,
                    viral_title,
                    description,
                    json.dumps(tags),
                    strategy_tier,
                    hook_dur,
                    pacing,
                    status,
                    token,
                    json.dumps(agent_results),
                ),
            )
            conn.commit()

        self._sync_queue_json()
        return self.get_staged_metadata(item_id)

    def get_staged_metadata(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM staged_metadata WHERE id = ?;", (item_id,)).fetchone()
            if not row:
                return None
            return self._row_to_metadata_dict(row)

    def list_staged_metadata(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM staged_metadata WHERE status = ? ORDER BY id DESC;", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM staged_metadata ORDER BY id DESC;").fetchall()
            return [self._row_to_metadata_dict(r) for r in rows]

    def confirm_metadata(self, item_id: int, token: Optional[str] = None) -> bool:
        """Mark video metadata as Confirmed with valid confirmation token."""
        with self._get_connection() as conn:
            if token:
                cur = conn.execute(
                    """
                    UPDATE staged_metadata
                    SET status = 'Confirmed', confirmation_token = ?
                    WHERE id = ?;
                    """,
                    (token, item_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE staged_metadata SET status = 'Confirmed' WHERE id = ?;", (item_id,)
                )
            conn.commit()
            updated = cur.rowcount > 0

        if updated:
            self._sync_queue_json()
        return updated

    def mark_metadata_published(self, item_id: int) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE staged_metadata SET status = 'Published' WHERE id = ?;", (item_id,)
            )
            conn.commit()
            updated = cur.rowcount > 0

        if updated:
            self._sync_queue_json()
        return updated

    def _row_to_metadata_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        tags = json.loads(d["tags"]) if d.get("tags") else []
        agent_results = json.loads(d["agent_results"]) if d.get("agent_results") else {}
        return {
            "id": d["id"],
            "timestamp": d["timestamp"],
            "ingestionSource": d["ingestion_source"],
            "rawInput": d["raw_input"],
            "metadata": {
                "viral_title": d["viral_title"],
                "title": d["viral_title"],
                "description": d["description"],
                "tags": tags,
                "strategy_tier": d["strategy_tier"],
            },
            "script": {
                "hookDuration": d["hook_duration"],
                "pacing": d["pacing"],
            },
            "agentResults": agent_results,
            "status": d["status"],
            "confirmation_token": d["confirmation_token"],
        }

    def _sync_queue_json(self) -> None:
        """Dual-write active items back to queue.json for exact backwards compatibility."""
        items = self.list_staged_metadata()
        try:
            self.queue_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to write to queue.json: {e}")

    # --------------------------------------------------------------------------
    # Comment Moderation & HITL Queue Operations
    # --------------------------------------------------------------------------

    def add_staged_comment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Stage an inbound YouTube comment for creator review."""
        rec_id = payload.get("id") or str(uuid.uuid4())
        cid = payload.get("comment_id") or f"cmt_{int(time.time() * 1000)}"
        vid = payload.get("video_id") or "M1G92FWmdJw"
        v_title = payload.get("video_title") or "Ayo's Den Episode"
        author = payload.get("author_name") or "Community Member"
        comment = payload.get("input_comment") or payload.get("text") or ""
        category = payload.get("category") or "BANTER"
        intent = payload.get("semiotic_intent") or "COMMUNITY_BANTER"
        energy = int(payload.get("energy_level") or 3)
        draft = payload.get("model_draft_reply") or payload.get("reply_text") or ""
        now = datetime.now(timezone.utc).isoformat()
        token = str(uuid.uuid4())

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO staged_comments (
                    id, comment_id, video_id, video_title, author_name,
                    input_comment, category, semiotic_intent, energy_level,
                    model_draft_reply, final_reply, status, confirmation_token,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    rec_id,
                    cid,
                    vid,
                    v_title,
                    author,
                    comment,
                    category,
                    intent,
                    energy,
                    draft,
                    draft,
                    "PENDING_APPROVAL",
                    token,
                    now,
                    now,
                ),
            )
            conn.commit()

        return self.get_staged_comment(rec_id)

    def get_staged_comment(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM staged_comments WHERE id = ?;", (record_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    def list_staged_comments(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM staged_comments WHERE status = ? ORDER BY created_at DESC;", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM staged_comments ORDER BY created_at DESC;").fetchall()
            return [dict(r) for r in rows]

    def update_comment_decision(
        self,
        record_id: str,
        status: str,
        final_reply: Optional[str] = None,
        human_verdict: Optional[str] = None,
        alignment_delta: float = 0.0,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE staged_comments
                SET status = ?, final_reply = coalesce(?, final_reply),
                    human_verdict = ?, alignment_delta = ?, updated_at = ?
                WHERE id = ?;
                """,
                (status, final_reply, human_verdict, alignment_delta, now, record_id),
            )
            conn.commit()
            return cur.rowcount > 0

    # --------------------------------------------------------------------------
    # Audit Event Ledger
    # --------------------------------------------------------------------------

    def record_audit_event(
        self,
        event_type: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        agent_invoked: bool = False,
        status: str = "SUCCESS",
        sanitization_flags: Optional[List[str]] = None,
        guard_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a structured JSON-RPC or tool invocation audit event."""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        args_json = json.dumps(arguments, ensure_ascii=False)
        res_json = json.dumps(result, ensure_ascii=False) if result is not None else None

        # Auto-extract guard_status and sanitization_flags if not explicitly supplied
        if guard_status is None and isinstance(result, dict) and "guard_status" in result:
            guard_status = result["guard_status"]
        if sanitization_flags is None and isinstance(result, dict) and "sanitization_flags" in result:
            sanitization_flags = result["sanitization_flags"]
        elif sanitization_flags is None and isinstance(result, dict) and "flags" in result and isinstance(result["flags"], list):
            sanitization_flags = result["flags"]
        elif sanitization_flags is None and isinstance(arguments, dict) and "sanitization_flags" in arguments:
            sanitization_flags = arguments["sanitization_flags"]

        sanit_flags_json = json.dumps(sanitization_flags) if sanitization_flags is not None else None

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, timestamp, event_type, tool_name, arguments, result, agent_invoked, status, sanitization_flags, guard_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (event_id, now, event_type, tool_name, args_json, res_json, int(agent_invoked), status, sanit_flags_json, guard_status),
            )
            conn.commit()

        return {
            "id": event_id,
            "timestamp": now,
            "event_type": event_type,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "agent_invoked": agent_invoked,
            "status": status,
            "sanitization_flags": sanitization_flags,
            "guard_status": guard_status,
        }

    def list_audit_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?;", (limit,)
            ).fetchall()
            events = []
            for r in rows:
                d = dict(r)
                s_flags = None
                if d.get("sanitization_flags"):
                    try:
                        s_flags = json.loads(d["sanitization_flags"])
                    except Exception:
                        s_flags = d["sanitization_flags"]

                events.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "event_type": d["event_type"],
                    "tool_name": d["tool_name"],
                    "arguments": json.loads(d["arguments"]) if d.get("arguments") else {},
                    "result": json.loads(d["result"]) if d.get("result") else None,
                    "agent_invoked": bool(d["agent_invoked"]),
                    "status": d["status"],
                    "sanitization_flags": s_flags,
                    "guard_status": d.get("guard_status"),
                })
            return events

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Full reactive snapshot of the studio workspace for WebMCP clients."""
        return {
            "staged_metadata": self.list_staged_metadata(),
            "staged_comments": self.list_staged_comments(),
            "recent_audit_events": self.list_audit_events(limit=25),
            "counts": {
                "metadata_staged": len(self.list_staged_metadata("Staged")),
                "metadata_confirmed": len(self.list_staged_metadata("Confirmed")),
                "comments_pending": len(self.list_staged_comments("PENDING_APPROVAL")),
            },
        }


# Global store instance
store = WebMcpStore()
