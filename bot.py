from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from dotenv import load_dotenv


load_dotenv()

RECENT_EVENTS: deque[dict[str, Any]] = deque(maxlen=100)
ACTIVE_SESSIONS: dict[str, "TwilioMediaSession"] = {}
PROJECT_ROOT = Path(__file__).resolve().parent
AUDIO_ASSETS_DIR = PROJECT_ROOT / "assets" / "audio"


@dataclass(frozen=True)
class PipelineConfig:
    llm_model: str
    worker_model: str
    nvidia_base_url: str
    stt_provider: str
    tts_provider: str
    turn_signal_digit: str = "#"


@dataclass
class TwilioMediaSession:
    session_id: str
    stream_sid: str | None = None
    call_sid: str | None = None
    caller: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    media_frames: int = 0
    inbound_audio_bytes: int = 0
    dtmf_digits: list[str] = field(default_factory=list)
    stopped: bool = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stream_sid": self.stream_sid,
            "call_sid": self.call_sid,
            "caller": self.caller,
            "started_at": self.started_at,
            "media_frames": self.media_frames,
            "inbound_audio_bytes": self.inbound_audio_bytes,
            "dtmf_digits": list(self.dtmf_digits),
            "stopped": self.stopped,
        }


def build_pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        llm_model=os.getenv("NVIDIA_LLM_MODEL", "nvidia/nemotron-3-super-120b"),
        worker_model=os.getenv("NVIDIA_WORKER_MODEL", "nvidia/nemotron-3-nano-30b"),
        nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        stt_provider="nvidia-nim" if os.getenv("NVIDIA_API_KEY") else "deepgram",
        tts_provider="nvidia-nim" if os.getenv("NVIDIA_API_KEY") else "cartesia",
    )


def _record_event(event_type: str, payload: dict[str, Any]) -> None:
    RECENT_EVENTS.append(
        {
            "at": datetime.now(UTC).isoformat(),
            "event": event_type,
            "payload": payload,
        }
    )


def get_recent_events() -> list[dict[str, Any]]:
    return list(RECENT_EVENTS)


def get_session_snapshot() -> list[dict[str, Any]]:
    return [session.snapshot() for session in ACTIVE_SESSIONS.values()]


def _payload_size(media_payload: str | None) -> int:
    if not media_payload:
        return 0
    return len(media_payload)


async def _send_ulaw_audio(websocket: Any, stream_sid: str, asset_name: str) -> None:
    asset_path = AUDIO_ASSETS_DIR / asset_name
    if not asset_path.exists():
        logger.warning("Audio asset missing: {}", asset_path)
        return

    payload = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    await websocket.send_text(
        json.dumps(
            {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload},
            }
        )
    )
    await websocket.send_text(
        json.dumps(
            {
                "event": "mark",
                "streamSid": stream_sid,
                "mark": {"name": asset_name},
            }
        )
    )
    _record_event("outbound_audio", {"stream_sid": stream_sid, "asset": asset_name})


async def run_bot(websocket: Any) -> None:
    """Entry point for the Twilio media stream.

    The production implementation will replace this loop with the Pipecat
    pipeline described in implementation_plan.md. Keeping this adapter thin
    lets the FastAPI/Twilio plumbing be tested before all voice services are
    configured.
    """

    config = build_pipeline_config()
    logger.info("Starting Safeline voice pipeline scaffold: {}", asdict(config))
    session = TwilioMediaSession(session_id=str(id(websocket)))
    ACTIVE_SESSIONS[session.session_id] = session
    _record_event("websocket_connected", {"session_id": session.session_id})

    try:
        while True:
            message = await websocket.receive_text()
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                logger.debug("Received non-JSON websocket message")
                continue

            event = payload.get("event")
            if event == "connected":
                logger.info("Twilio WebSocket protocol connected")
                _record_event("connected", {"session_id": session.session_id})
            elif event == "start":
                start = payload.get("start", {})
                session.stream_sid = start.get("streamSid")
                session.call_sid = start.get("callSid")
                parameters = start.get("customParameters", {})
                session.caller = parameters.get("caller")
                logger.info(
                    "Twilio stream started: stream_sid={} call_sid={} caller={}",
                    session.stream_sid,
                    session.call_sid,
                    session.caller,
                )
                _record_event("start", session.snapshot())
                if session.stream_sid:
                    await _send_ulaw_audio(websocket, session.stream_sid, "phase1_prompt.ulaw")
            elif event == "dtmf":
                digit = payload.get("dtmf", {}).get("digit")
                if digit:
                    session.dtmf_digits.append(digit)
                logger.info("Received DTMF digit: {}", digit)
                _record_event("dtmf", {"stream_sid": session.stream_sid, "digit": digit})
                if digit == config.turn_signal_digit and session.stream_sid:
                    await _send_ulaw_audio(websocket, session.stream_sid, "phase1_ack.ulaw")
            elif event == "media":
                media = payload.get("media", {})
                session.media_frames += 1
                session.inbound_audio_bytes += _payload_size(media.get("payload"))
                if session.media_frames == 1 or session.media_frames % 250 == 0:
                    logger.info(
                        "Receiving inbound audio: frames={} encoded_bytes={}",
                        session.media_frames,
                        session.inbound_audio_bytes,
                    )
                    _record_event(
                        "media",
                        {
                            "stream_sid": session.stream_sid,
                            "frames": session.media_frames,
                            "encoded_bytes": session.inbound_audio_bytes,
                        },
                    )
            elif event == "mark":
                _record_event("mark", payload.get("mark", {}))
            elif event == "stop":
                session.stopped = True
                logger.info("Twilio stream stopped: {}", session.snapshot())
                _record_event("stop", session.snapshot())
                break
            else:
                logger.debug("Unhandled Twilio event: {}", payload)
    finally:
        ACTIVE_SESSIONS.pop(session.session_id, None)
        _record_event("websocket_disconnected", session.snapshot())
