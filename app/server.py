"""FastAPI Server exposing WebSocket JSON-RPC 2.0 WebMCP bridge and REST API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import config
from app.store import store
from app.tools import run_autonomous_pipeline
from app.ws_bridge import handle_webmcp_message, manager

app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="Unified Google ADK Agent Backend & Browser-Native WebMCP Bridge for Ayo's Den & IoChat Studio.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class PipelineRunRequest(BaseModel):
    source: str = "Reddit_r_KATSEYE"
    raw_text: str = "Detroit show canceled after soundcheck, fans demanding answers and refunds"
    competitor_views: int = 15000
    competitor_hours: float = 2.0


# --------------------------------------------------------------------------
# WebSocket WebMCP Bridge (/ws/webmcp)
# --------------------------------------------------------------------------

@app.websocket("/ws/webmcp")
async def websocket_webmcp_endpoint(websocket: WebSocket):
    """Browser-Native WebMCP JSON-RPC 2.0 endpoint."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await handle_webmcp_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


# --------------------------------------------------------------------------
# REST Endpoints
# --------------------------------------------------------------------------

@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    snapshot = store.get_state_snapshot()
    return {
        "status": "healthy",
        "service": config.app_name,
        "version": config.app_version,
        "target_channel": config.target_channel,
        "active_ws_connections": len(manager.active_connections),
        "counts": snapshot["counts"],
    }


@app.get("/api/queue")
def get_queue() -> list[Dict[str, Any]]:
    """Backwards-compatible REST endpoint returning queue.json entries."""
    return store.list_staged_metadata()


@app.get("/api/state")
def get_full_state() -> Dict[str, Any]:
    """Returns complete state snapshot."""
    return store.get_state_snapshot()


@app.post("/api/pipeline/run")
def trigger_pipeline(req: PipelineRunRequest) -> Dict[str, Any]:
    """Triggers the 4-agent autonomous pipeline and returns staged result."""
    result = run_autonomous_pipeline(
        source=req.source,
        raw_text=req.raw_text,
        competitor_views=req.competitor_views,
        competitor_hours=req.competitor_hours,
    )
    return {
        "status": "success",
        "message": "Autonomous 4-agent cycle executed and staged in WebMcpStore.",
        "payload": result,
    }


# --------------------------------------------------------------------------
# Frontend Dashboard Delivery
# --------------------------------------------------------------------------

if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def serve_frontend_dist():
        return HTMLResponse((FRONTEND_DIST / "index.html").read_text(encoding="utf-8"))
else:
    # Embedded fallback Command Deck so the deck is immediately usable out of the box
    @app.get("/", response_class=HTMLResponse)
    def serve_fallback_deck():
        deck_html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
        if deck_html_path.exists():
            return HTMLResponse(deck_html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Ayo's Den Studio Command Deck initializing...</h1>")
