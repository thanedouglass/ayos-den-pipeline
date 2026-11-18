"""Integration tests for WebMCP JSON-RPC 2.0 protocol and WebSocket bridge."""

import pytest
from fastapi.testclient import TestClient
from app.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["target_channel"] == "Ayo's Den"


def test_api_queue_and_pipeline(client):
    res_run = client.post("/api/pipeline/run", json={
        "source": "Reddit_Test_Client",
        "raw_text": "Live test of pipeline endpoint",
        "competitor_views": 20000,
        "competitor_hours": 2.0,
    })
    assert res_run.status_code == 200
    payload = res_run.json()["payload"]
    assert payload["status"] == "Staged"

    res_q = client.get("/api/queue")
    assert res_q.status_code == 200
    items = res_q.json()
    assert any(item["id"] == payload["id"] for item in items)


def receive_rpc_response(ws, expected_id):
    """Helper that reads messages until receiving the JSON-RPC response with matching id."""
    while True:
        msg = ws.receive_json()
        if msg.get("id") == expected_id:
            return msg


def test_websocket_webmcp_rpc(client):
    with client.websocket_connect("/ws/webmcp") as ws:
        # Initial snapshot sent upon connect
        init_snapshot = ws.receive_json()
        assert init_snapshot["method"] == "state/snapshot"

        # 1. initialize
        ws.send_json({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        res_init = receive_rpc_response(ws, 1)
        assert res_init["id"] == 1
        assert "tools" in res_init["result"]
        assert res_init["result"]["capabilities"]["forms"] is True

        # 2. tools/list
        ws.send_json({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        res_tools = receive_rpc_response(ws, 2)
        assert res_tools["id"] == 2
        tool_names = [t["name"] for t in res_tools["result"]["tools"]]
        assert "sentiment_indexer" in tool_names
        assert "publish_video_metadata" in tool_names
        assert "poll_reddit_and_velocity" in tool_names
        assert "grade_short_package" in tool_names
        assert "triage_and_grade_comment" in tool_names

        # 3. tools/call with deterministic guardrail check
        ws.send_json({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "publish_video_metadata",
                "arguments": {
                    "metadata_id": 9999,
                    "video_id": "test_vid",
                    "title": "Unapproved",
                    "description": "Desc",
                    "tags": ["test"],
                    "user_confirmed": False,
                },
                "agentInvoked": False,
            },
        })
        res_call = receive_rpc_response(ws, 3)
        assert res_call["id"] == 3
        # Must be halted by guard
        assert res_call["result"]["guard_status"] == "CONFIRMATION_REQUIRED"

        # 4. forms/submit with SubmitEvent.agentInvoked flag
        ws.send_json({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "forms/submit",
            "params": {
                "toolname": "stage_video_metadata",
                "data": {
                    "viral_title": "Declarative Form Staged Hook 🚀 #Shorts",
                    "description": "SEO description",
                    "tags": "KATSEYE, Shorts",
                    "strategy_tier": "FEED_FUEL",
                    "hookDuration": "3s",
                },
                "agentInvoked": True,
            },
        })
        res_form = receive_rpc_response(ws, 4)
        assert res_form["id"] == 4
        assert res_form["result"]["status"] == "Staged"
