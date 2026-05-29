from __future__ import annotations

from typing import Any

from agents.base_report import build_structured_report


async def generate_incident_report(
    transcript: str,
    extraction: dict[str, Any],
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_structured_report("incident_report", transcript, extraction, corrections)

