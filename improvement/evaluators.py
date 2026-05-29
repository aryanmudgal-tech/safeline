from __future__ import annotations

from typing import Any

from agents.base_report import missing_value
from agents.consistency_checker import check_consistency


def report_completeness(template: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    required_fields = [field for field in template.get("fields", []) if field.get("required")]
    report_fields = report.get("fields", {})
    missing = []

    for field in required_fields:
        value = report_fields.get(field["name"])
        unavailable = isinstance(value, dict) and value.get("status") == "not_available"
        if missing_value(value) or unavailable:
            missing.append(field["name"])

    total = len(required_fields)
    score = 1.0 if total == 0 else (total - len(missing)) / total
    return {"score": score, "missing_required_fields": missing}


def cross_document_consistency(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings = check_consistency(reports)
    return {"score": 1.0 if not findings else 0.0, "findings": findings}


def question_coverage(missing_fields_before_questions: list[str], asked_fields: list[str]) -> dict[str, Any]:
    missing = set(missing_fields_before_questions)
    asked = set(asked_fields)
    uncovered = sorted(missing - asked)
    score = 1.0 if not missing else (len(missing) - len(uncovered)) / len(missing)
    return {"score": score, "uncovered_fields": uncovered}

