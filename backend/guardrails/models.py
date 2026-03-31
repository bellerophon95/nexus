from typing import Any

from pydantic import BaseModel


class GuardResult(BaseModel):
    passed: bool
    sanitized_content: str
    blocked_reason: str | None = None
    pii_detected: list[str] = []
    hallucination_score: float = 0.0
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
