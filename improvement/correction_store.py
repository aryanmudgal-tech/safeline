from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Correction:
    report_type: str
    transcript: str
    original: dict[str, Any]
    corrected: dict[str, Any]
    category: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorrectionStore:
    """Small in-memory retrieval store for the hackathon scaffold.

    Production should replace token overlap with sentence-transformers + FAISS,
    as described in the implementation plan.
    """

    def __init__(self) -> None:
        self._corrections: list[Correction] = []

    def add_correction(
        self,
        report_type: str,
        transcript: str,
        original: dict[str, Any],
        corrected: dict[str, Any],
        category: str,
        metadata: dict[str, Any] | None = None,
    ) -> Correction:
        correction = Correction(
            report_type=report_type,
            transcript=transcript,
            original=original,
            corrected=corrected,
            category=category,
            metadata=metadata or {},
        )
        self._corrections.append(correction)
        return correction

    def get_similar_corrections(
        self,
        report_type: str,
        transcript: str,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        query_tokens = _tokens(transcript)
        scored: list[tuple[float, Correction]] = []

        for correction in self._corrections:
            if correction.report_type != report_type:
                continue
            correction_tokens = _tokens(correction.transcript)
            score = _jaccard(query_tokens, correction_tokens)
            scored.append((score, correction))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [correction.to_dict() for score, correction in scored[:k] if score > 0]


def _tokens(text: str) -> set[str]:
    return {token.strip(".,:;!?()[]{}\"'").lower() for token in text.split() if token}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)

