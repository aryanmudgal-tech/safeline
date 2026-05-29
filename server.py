from __future__ import annotations

import os
from html import escape
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from loguru import logger
from dotenv import load_dotenv

from bot import get_recent_events, get_session_snapshot, run_bot
from review_ui.api import router as review_router


load_dotenv()

app = FastAPI(title="Safeline Voice Documentation Agent", version="0.1.0")
app.include_router(review_router, prefix="/api")
app.mount("/review", StaticFiles(directory="review_ui", html=True), name="review")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "safeline"}


@app.get("/phase1/status")
async def phase1_status() -> dict[str, Any]:
    return {
        "service": "safeline",
        "phase": "phase_1_twilio_media_stream",
        "twilio_phone_number_configured": bool(os.getenv("TWILIO_PHONE_NUMBER")),
        "public_websocket_url_configured": bool(os.getenv("TWILIO_PUBLIC_WS_URL")),
        "active_sessions": get_session_snapshot(),
        "recent_events": get_recent_events(),
    }


def _public_http_url(request: Request) -> str:
    configured_ws_url = os.getenv("TWILIO_PUBLIC_WS_URL")
    if configured_ws_url:
        return configured_ws_url.replace("wss://", "https://").replace("ws://", "http://").rsplit("/", 2)[0]

    configured_app_url = os.getenv("APP_BASE_URL")
    if configured_app_url and not configured_app_url.startswith("http://localhost"):
        return configured_app_url.rstrip("/")

    host = request.headers.get("host", request.url.netloc)
    return f"{request.url.scheme}://{host}"


def _twilio_stream_url(request: Request) -> str:
    configured_url = os.getenv("TWILIO_PUBLIC_WS_URL")
    if configured_url:
        return configured_url

    host = request.headers.get("host", request.url.netloc)
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{host}/ws/twilio"


@app.get("/twilio/voice")
@app.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    form = await request.form() if request.method == "POST" else {}
    caller = escape(str(form.get("From", "unknown")))
    stream_url = escape(_twilio_stream_url(request))
    status_callback_url = escape(f"{_public_http_url(request)}/twilio/stream-status")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Safeline is connected. Please wait while I open the secure documentation line.</Say>
  <Connect>
    <Stream url="{stream_url}" statusCallback="{status_callback_url}" statusCallbackMethod="POST">
      <Parameter name="caller" value="{caller}" />
      <Parameter name="phase" value="phase_1" />
    </Stream>
  </Connect>
</Response>
"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/stream-status")
async def twilio_stream_status(request: Request) -> dict[str, Any]:
    form = await request.form()
    payload = {key: str(value) for key, value in form.items()}
    logger.info("Twilio stream status callback: {}", payload)
    return {"ok": True}


@app.post("/twilio/call-status")
async def twilio_call_status(request: Request) -> dict[str, Any]:
    form = await request.form()
    payload = {key: str(value) for key, value in form.items()}
    logger.info("Twilio call status callback: {}", payload)
    return {"ok": True}


@app.websocket("/ws/twilio")
async def twilio_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await run_bot(websocket)
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
