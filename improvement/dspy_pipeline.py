from __future__ import annotations

import os
from typing import Any


def configure_dspy() -> Any:
    """Configure DSPy for NVIDIA NIM when dspy-ai is installed."""

    try:
        import dspy
    except ImportError as exc:
        raise RuntimeError("Install dspy-ai before configuring DSPy.") from exc

    lm = dspy.LM(
        model=os.getenv("NVIDIA_LLM_MODEL", "nvidia/nemotron-3-super-120b"),
        api_base=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY"),
    )
    dspy.configure(lm=lm)
    return dspy


def build_few_shot_context(corrections: list[dict[str, Any]]) -> str:
    if not corrections:
        return ""

    examples = []
    for correction in corrections:
        examples.append(
            "\n".join(
                [
                    f"Category: {correction.get('category')}",
                    f"Original: {correction.get('original')}",
                    f"Corrected: {correction.get('corrected')}",
                ]
            )
        )
    return "\n\n".join(examples)

