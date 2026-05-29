from __future__ import annotations

from typing import Any


REPORT_INDICATORS = {
    "arrest_report": {
        "fields": ("arrested", "charges", "miranda_given"),
        "keywords": ("arrest", "custody", "handcuff", "booked", "charge", "miranda"),
    },
    "use_of_force": {
        "fields": ("force_used", "force_details"),
        "keywords": ("force", "tased", "taser", "struck", "restrain", "resist", "pepper spray"),
    },
    "accident_report": {
        "fields": ("vehicles",),
        "keywords": ("collision", "crash", "accident", "vehicle damage", "traffic accident"),
    },
}


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _truthy_extraction_signal(extraction: dict[str, Any], field: str) -> bool:
    if field == "arrested":
        return any(subject.get("arrested") for subject in extraction.get("subjects", []))
    value = extraction.get(field)
    return bool(value)


def suggest_report_types(extraction: dict[str, Any], transcript: str = "") -> list[str]:
    text = f"{transcript} {_flatten_text(extraction)}".lower()
    suggestions = ["incident_report"]

    for report_type, indicators in REPORT_INDICATORS.items():
        has_field_signal = any(
            _truthy_extraction_signal(extraction, field)
            for field in indicators["fields"]
        )
        has_keyword_signal = any(keyword in text for keyword in indicators["keywords"])
        if has_field_signal or has_keyword_signal:
            suggestions.append(report_type)

    return suggestions

