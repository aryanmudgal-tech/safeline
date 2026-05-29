from __future__ import annotations

import os
from typing import Any


class DynamoDBStore:
    """DynamoDB adapter with an in-memory mode for local demo work."""

    def __init__(self, use_aws: bool = False) -> None:
        self.use_aws = use_aws
        self.incidents_table = os.getenv("AWS_DYNAMODB_INCIDENTS_TABLE", "safeline-incidents")
        self.corrections_table = os.getenv("AWS_DYNAMODB_CORRECTIONS_TABLE", "safeline-corrections")
        self._incidents: dict[str, dict[str, Any]] = {}
        self._corrections: list[dict[str, Any]] = []

        self._resource = None
        if use_aws:
            import boto3

            self._resource = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

    async def put_incident(self, incident_id: str, incident: dict[str, Any]) -> None:
        if self._resource:
            self._resource.Table(self.incidents_table).put_item(Item={"incident_id": incident_id, **incident})
            return
        self._incidents[incident_id] = incident

    async def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        if self._resource:
            response = self._resource.Table(self.incidents_table).get_item(Key={"incident_id": incident_id})
            return response.get("Item")
        return self._incidents.get(incident_id)

    async def put_correction(self, correction: dict[str, Any]) -> None:
        if self._resource:
            self._resource.Table(self.corrections_table).put_item(Item=correction)
            return
        self._corrections.append(correction)

    async def list_corrections(self) -> list[dict[str, Any]]:
        return list(self._corrections)

