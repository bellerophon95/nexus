import logging
import re

from backend.guardrails.models import GuardResult

logger = logging.getLogger(__name__)

_profanity_loaded = False

# ---------------------------------------------------------------------------
# Regex-based PII filter — replaces Presidio (~500MB RAM) with zero-RAM patterns.
# Covers the most common PII types: email, phone, SSN, credit cards, IPs.
# ---------------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "EMAIL_ADDRESS",
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    ),
    ("PHONE_NUMBER", re.compile(r"(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")),
    ("US_SSN", re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ \-]?){13,16}\b")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]

_PII_REDACT_MAP = {
    "EMAIL_ADDRESS": "<EMAIL>",
    "PHONE_NUMBER": "<PHONE>",
    "US_SSN": "<SSN>",
    "CREDIT_CARD": "<CREDIT_CARD>",
    "IP_ADDRESS": "<IP>",
}


def _regex_pii_filter(text: str) -> tuple[str, list[str]]:
    """
    Detects and redacts common PII using regex patterns.
    Returns (sanitized_text, list_of_detected_pii_types).
    Zero RAM overhead — no models loaded.
    """
    detected = []
    sanitized = text
    for pii_type, pattern in _PII_PATTERNS:
        if pattern.search(sanitized):
            detected.append(pii_type)
            sanitized = pattern.sub(_PII_REDACT_MAP[pii_type], sanitized)
    return sanitized, detected


# Prompt Injection Patterns (Lightweight Regex style)
INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"system override",
    r"new instructions:",
    r"you are now a",
    r"forget everything you (know|learnt)",
    r"reveal your system prompt",
    r"disregard (any|all) constraints",
]


def get_profanity():
    """Lazy loader for better_profanity."""
    global _profanity_loaded
    from better_profanity import profanity

    if not _profanity_loaded:
        whitelist = ["dummy", "mock", "stub", "lorem", "ipsum", "test", "demo"]
        profanity.load_censor_words(whitelist_words=whitelist)
        _profanity_loaded = True
    return profanity


def run_input_guardrails(query: str) -> GuardResult:
    """
    Screens incoming queries for prompt injection, PII, and profanity.
    Uses lightweight regex for PII — no NLP models loaded on startup.
    """
    from backend.config import settings

    # 1. Profanity Check (Fast)
    profanity = get_profanity()
    if profanity.contains_profanity(query):
        logger.warning(f"Profanity detected in query: {query[:50]}...")
        return GuardResult(
            passed=False,
            sanitized_content=query,
            blocked_reason="Safety violation: Profanity detected.",
            metadata={"guardrail": "profanity"},
        )

    # 2. Prompt Injection Check (Fast / Regex)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query.lower()):
            logger.warning(f"Prompt injection detected for pattern: {pattern}")
            return GuardResult(
                passed=False,
                sanitized_content=query,
                blocked_reason="Security violation: Potential prompt injection detected.",
                metadata={"detected_pattern": pattern, "guardrail": "injection"},
            )

    # 3. PII Detection (Regex — replaces Presidio)
    sanitized_query, pii_types = _regex_pii_filter(query)
    if pii_types:
        logger.info(f"PII detected and redacted: {pii_types}")

    return GuardResult(
        passed=True,
        sanitized_content=sanitized_query,
        pii_detected=pii_types,
        metadata={"pii_count": len(pii_types), "guardrail": "passed", "mode": settings.ENV},
    )
