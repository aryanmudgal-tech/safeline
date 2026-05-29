from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from agents.accident_report import generate_accident_report
from agents.arrest_report import generate_arrest_report
from agents.base_report import get_nested_value, load_template, missing_value
from agents.incident_report import generate_incident_report
from agents.report_router import suggest_report_types
from agents.use_of_force import generate_use_of_force_report
from flows import initial_extraction_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]


ORCHESTRATOR_SYSTEM_PROMPT = """You are Safeline, a police documentation assistant.
Help officers create accurate, complete reports through natural conversation.
During OPEN_NARRATIVE, listen without interruption and extract facts silently.
During REPORT_SUGGESTION, recommend needed report types and ask the officer to confirm.
During GAP_FILLING, ask one question at a time, prioritizing legal requirements, identity,
timeline, evidence, and administrative details. Never invent facts."""


TOOL_DEFINITIONS = [
    {
        "name": "lookup_officer",
        "description": "Look up officer details by badge number from the roster.",
        "parameters": {"badge_number": "string"},
    },
    {
        "name": "check_missing_fields",
        "description": "Check missing required fields for a given report type.",
        "parameters": {"report_type": "string"},
    },
    {
        "name": "update_extracted_data",
        "description": "Update the structured extraction state.",
        "parameters": {"field": "string", "value": "any", "source": "string"},
    },
    {
        "name": "get_report_suggestions",
        "description": "Suggest report types based on extracted entities.",
        "parameters": {},
    },
    {
        "name": "trigger_document_generation",
        "description": "Trigger parallel document generation for approved report types.",
        "parameters": {"report_types": "array[string]"},
    },
]


def create_empty_extraction() -> dict[str, Any]:
    return initial_extraction_state()


def lookup_officer(badge_number: str) -> dict[str, Any] | None:
    roster_path = PROJECT_ROOT / "mock_data" / "officer_roster.json"
    with roster_path.open("r", encoding="utf-8") as handle:
        officers = json.load(handle)
    return next((officer for officer in officers if officer["badge"] == badge_number), None)


def update_extracted_data(
    extraction: dict[str, Any],
    field: str,
    value: Any,
    source: str,
) -> dict[str, Any]:
    updated = deepcopy(extraction)
    current: dict[str, Any] = updated
    parts = field.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value
    updated.setdefault("_sources", {})[field] = source
    return updated


def check_missing_fields(report_type: str, extraction: dict[str, Any]) -> list[dict[str, Any]]:
    template = load_template(report_type)
    priority_order = {
        "legal": 0,
        "identity": 1,
        "timeline": 2,
        "evidence": 3,
        "administrative": 4,
    }
    missing: list[dict[str, Any]] = []

    for field in template.get("fields", []):
        if not field.get("required"):
            continue

        value = get_nested_value(extraction, field.get("source"))
        if missing_value(value):
            missing.append(
                {
                    "name": field["name"],
                    "label": field["label"],
                    "priority": field.get("priority", "administrative"),
                    "question": field.get("question"),
                }
            )

    return sorted(missing, key=lambda item: priority_order.get(item["priority"], 99))


def get_report_suggestions(extraction: dict[str, Any], transcript: str = "") -> list[str]:
    return suggest_report_types(extraction, transcript)


async def trigger_document_generation(
    report_types: list[str],
    transcript: str,
    extraction: dict[str, Any],
    corrections: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    generators = {
        "incident_report": generate_incident_report,
        "arrest_report": generate_arrest_report,
        "use_of_force": generate_use_of_force_report,
        "accident_report": generate_accident_report,
    }

    tasks = []
    for report_type in report_types:
        generator = generators[report_type]
        report_corrections = (corrections or {}).get(report_type, [])
        tasks.append(generator(transcript, extraction, report_corrections))

    generated = await asyncio.gather(*tasks)
    return {report["report_type"]: report for report in generated}

