from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class GuardResult(BaseModel):
    passed: bool
    sanitized_content: str
    blocked_reason: Optional[str] = None
    pii_detected: List[str] = []
    hallucination_score: float = 0.0
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}
