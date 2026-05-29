from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(tags=["review"])


DEMO_INCIDENT_ID = "INC-DEMO-0001"
DEMO_DOCUMENTS: dict[str, dict[str, Any]] = {
    "incident_report": {
        "report_type": "incident_report",
        "title": "Incident Report",
        "fields": {
            "reporting_officer": "Officer Elena Martinez",
            "badge_number": "4521",
            "incident_date": "2026-05-30",
            "incident_time": "02:15",
            "incident_location": "142 Oak Street",
            "incident_type": "domestic_disturbance",
            "involved_parties": "Adult male suspect and adult female victim",
            "witnesses": "Neighbor at 144 Oak Street",
            "evidence": "Body camera, 911 call notes",
            "injuries": "Minor redness on victim's forearm",
        },
        "narrative": {
            "draft": "Officer Martinez responded to a domestic disturbance at 142 Oak Street and detained the suspect after observing signs of a physical altercation."
        },
    }
}
APPROVALS: dict[str, list[dict[str, Any]]] = {}


class ApprovalRequest(BaseModel):
    officer_version: dict[str, Any]
    approved_by: str


@router.get("/incidents/{incident_id}/documents")
async def get_documents(incident_id: str) -> dict[str, Any]:
    if incident_id != DEMO_INCIDENT_ID:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": incident_id,
        "documents": deepcopy(DEMO_DOCUMENTS),
        "transcript": "Dispatch assigned me to 142 Oak Street for a domestic disturbance...",
    }


@router.post("/incidents/{incident_id}/documents/{report_type}/approve")
async def approve_document(
    incident_id: str,
    report_type: str,
    approval: ApprovalRequest,
) -> dict[str, Any]:
    if incident_id != DEMO_INCIDENT_ID or report_type not in DEMO_DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")

    original = DEMO_DOCUMENTS[report_type]
    officer_version = approval.officer_version
    diff = _compute_diff(original, officer_version)
    record = {
        "incident_id": incident_id,
        "report_type": report_type,
        "approved_by": approval.approved_by,
        "approved_at": datetime.now(UTC).isoformat(),
        "original_draft": original,
        "officer_version": officer_version,
        "diff": diff,
    }
    APPROVALS.setdefault(incident_id, []).append(record)
    return {"status": "approved", "approval": record}


@router.get("/incidents/{incident_id}/approvals")
async def get_approvals(incident_id: str) -> dict[str, Any]:
    return {"incident_id": incident_id, "approvals": APPROVALS.get(incident_id, [])}


def _compute_diff(original: dict[str, Any], officer_version: dict[str, Any]) -> dict[str, Any]:
    try:
        from deepdiff import DeepDiff

        return DeepDiff(original, officer_version, ignore_order=True).to_dict()
    except ImportError:
        return {
            "changed": original != officer_version,
            "original_keys": sorted(original.keys()),
            "officer_version_keys": sorted(officer_version.keys()),
        }

