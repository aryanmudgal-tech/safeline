from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from loguru import logger


@dataclass(frozen=True)
class PipelineConfig:
    llm_model: str
    worker_model: str
    nvidia_base_url: str
    stt_provider: str
    tts_provider: str
    turn_signal_digit: str = "#"


def build_pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        llm_model=os.getenv("NVIDIA_LLM_MODEL", "nvidia/nemotron-3-super-120b"),
        worker_model=os.getenv("NVIDIA_WORKER_MODEL", "nvidia/nemotron-3-nano-30b"),
        nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        stt_provider="nvidia-nim" if os.getenv("NVIDIA_API_KEY") else "deepgram",
        tts_provider="nvidia-nim" if os.getenv("NVIDIA_API_KEY") else "cartesia",
    )


async def run_bot(websocket: Any) -> None:
    """Entry point for the Twilio media stream.

    The production implementation will replace this loop with the Pipecat
    pipeline described in implementation_plan.md. Keeping this adapter thin
    lets the FastAPI/Twilio plumbing be tested before all voice services are
    configured.
    """

    config = build_pipeline_config()
    logger.info("Starting Safeline voice pipeline scaffold: {}", asdict(config))

    while True:
        message = await websocket.receive_text()
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("Received non-JSON websocket message")
            continue

        event = payload.get("event")
        if event == "start":
            logger.info("Twilio stream started: {}", payload.get("start", {}).get("streamSid"))
        elif event == "dtmf":
            digit = payload.get("dtmf", {}).get("digit")
            logger.info("Received DTMF digit: {}", digit)
        elif event == "media":
            continue
        elif event == "stop":
            logger.info("Twilio stream stopped")
            break

