"""Unit tests for WebMcpStore and queue.json synchronization."""

import json
import tempfile
from pathlib import Path
from app.store import WebMcpStore


def test_store_metadata_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_studio.db"
        queue_path = Path(tmpdir) / "queue.json"

        store = WebMcpStore(db_path=db_path, queue_path=queue_path)

        # 1. Add staged metadata
        payload = {
            "id": 123456789,
            "ingestionSource": "TestFeed",
            "rawInput": "KATSEYE Detroit show updates",
            "metadata": {
                "viral_title": "KATSEYE Detroit Show Update 🚨 #Shorts",
                "description": "Full breakdown of Detroit venue changes.",
                "tags": ["KATSEYE", "Shorts"],
                "strategy_tier": "FEED_FUEL",
            },
            "script": {
                "hookDuration": "3 seconds",
                "pacing": "Fast pivot",
            },
            "status": "Staged",
        }

        saved = store.add_staged_metadata(payload)
        assert saved["id"] == 123456789
        assert saved["status"] == "Staged"
        assert saved["metadata"]["viral_title"] == "KATSEYE Detroit Show Update 🚨 #Shorts"

        # Verify queue.json was synchronized
        assert queue_path.exists()
        queue_data = json.loads(queue_path.read_text(encoding="utf-8"))
        assert len(queue_data) == 1
        assert queue_data[0]["id"] == 123456789

        # 2. Confirm metadata
        confirmed = store.confirm_metadata(123456789)
        assert confirmed is True
        item = store.get_staged_metadata(123456789)
        assert item["status"] == "Confirmed"

        # 3. Mark published
        published = store.mark_metadata_published(123456789)
        assert published is True
        item = store.get_staged_metadata(123456789)
        assert item["status"] == "Published"


def test_store_comment_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_studio.db"
        queue_path = Path(tmpdir) / "queue.json"

        store = WebMcpStore(db_path=db_path, queue_path=queue_path)

        # Add comment
        comment_payload = {
            "comment_id": "cmt_999",
            "video_id": "vid_123",
            "video_title": "KATSEYE Dance Cover",
            "author_name": "@viewer",
            "input_comment": "that footwork at 0:15 was insane!",
            "category": "DANCE_CHOREO",
            "semiotic_intent": "CHOREO_TECHNIQUE_INQUIRY",
            "energy_level": 4,
            "model_draft_reply": "That transition took 40 studio takes!",
        }

        saved = store.add_staged_comment(comment_payload)
        assert saved["comment_id"] == "cmt_999"
        assert saved["status"] == "PENDING_APPROVAL"

        # Update decision
        updated = store.update_comment_decision(
            record_id=saved["id"],
            status="APPROVED",
            final_reply="That transition took 40 studio takes!",
            human_verdict="approve",
        )
        assert updated is True

        c = store.get_staged_comment(saved["id"])
        assert c["status"] == "APPROVED"
        assert c["human_verdict"] == "approve"


def test_store_audit_event_logging():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_studio.db"
        queue_path = Path(tmpdir) / "queue.json"

        store = WebMcpStore(db_path=db_path, queue_path=queue_path)

        event = store.record_audit_event(
            event_type="TOOL_CALLED",
            tool_name="sentiment_indexer",
            arguments={"raw_text": "testing discourse"},
            result={"sparkDetected": True},
            agent_invoked=True,
            status="SUCCESS",
        )

        assert event["id"].startswith("evt_")
        assert event["agent_invoked"] is True

        events = store.list_audit_events()
        assert len(events) == 1
        assert events[0]["tool_name"] == "sentiment_indexer"
        assert events[0]["agent_invoked"] is True
