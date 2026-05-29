from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class S3Store:
    """S3 adapter with local JSON file fallback."""

    def __init__(self, use_aws: bool = False, local_root: str = "tmp/s3") -> None:
        self.use_aws = use_aws
        self.bucket = os.getenv("AWS_S3_BUCKET", "safeline-documents")
        self.local_root = Path(local_root)
        self._client = None

        if use_aws:
            import boto3

            self._client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

    async def put_json(self, key: str, payload: dict[str, Any]) -> str:
        if self._client:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(payload).encode("utf-8"),
                ContentType="application/json",
            )
            return f"s3://{self.bucket}/{key}"

        target = self.local_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(target)

    async def get_json(self, key: str) -> dict[str, Any]:
        if self._client:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))

        return json.loads((self.local_root / key).read_text(encoding="utf-8"))

