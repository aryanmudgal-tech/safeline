from __future__ import annotations

from typing import Any


CONSISTENCY_ALIASES = {
    "incident_date": ("incident_date", "arrest_date", "force_date", "accident_date"),
    "incident_location": ("incident_location", "arrest_location", "force_location", "accident_location"),
    "suspect_name": ("suspect_name", "primary_subject_name"),
}


def _field_value(report: dict[str, Any], field_name: str) -> Any:
    value = report.get("fields", {}).get(field_name)
    if isinstance(value, dict) and value.get("status") == "not_available":
        return None
    return value


def check_consistency(reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for canonical_field, aliases in CONSISTENCY_ALIASES.items():
        observed: dict[str, Any] = {}
        for report_type, report in reports.items():
            for alias in aliases:
                value = _field_value(report, alias)
                if value:
                    observed[report_type] = value
                    break

        unique_values = {str(value).strip().lower() for value in observed.values()}
        if len(unique_values) > 1:
            findings.append(
                {
                    "field": canonical_field,
                    "severity": "review",
                    "message": f"Mismatched {canonical_field} across generated reports.",
                    "observed": observed,
                }
            )

    return findings

