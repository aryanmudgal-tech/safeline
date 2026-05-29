from __future__ import annotations

import os
from html import escape

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from loguru import logger

from bot import run_bot
from review_ui.api import router as review_router


app = FastAPI(title="Safeline Voice Documentation Agent", version="0.1.0")
app.include_router(review_router, prefix="/api")
app.mount("/review", StaticFiles(directory="review_ui", html=True), name="review")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "safeline"}


def _twilio_stream_url(request: Request) -> str:
    configured_url = os.getenv("TWILIO_PUBLIC_WS_URL")
    if configured_url:
        return configured_url

    host = request.headers.get("host", request.url.netloc)
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{host}/ws/twilio"


@app.post("/twilio/voice")
async def twilio_voice(request: Request) -> Response:
    form = await request.form()
    caller = escape(str(form.get("From", "unknown")))
    stream_url = escape(_twilio_stream_url(request))

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{stream_url}">
      <Parameter name="caller" value="{caller}" />
    </Stream>
  </Connect>
</Response>
"""
    return Response(content=twiml, media_type="application/xml")


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

