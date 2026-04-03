import logging
from typing import Any

from backend.guardrails.models import GuardResult
from backend.observability.tracing import observe
from backend.retrieval.self_rag import check_hallucination

logger = logging.getLogger(__name__)

# Lazily initialize Presidio and Profanity to prevent blocking imports
_analyzer = None
_profanity_loaded = False

# Expanded whitelist to prevent false positives with dummy text and Markdown syntax
TECHNICAL_WHITELIST = [
    "dummy",
    "mock",
    "stub",
    "lorem",
    "ipsum",
    "answer",
    "sources",
    "citations",
    "references",
    "context",
    "synthetic",
    "testing",
    "development",
]

# PII types severe enough to block the response outright
HIGH_SEVERITY_PII = {"CREDIT_CARD", "US_SSN", "PASSWORD", "CRYPTO", "IBAN_CODE"}

# Hallucination score above this threshold causes the guardrail to fail
HALLUCINATION_BLOCK_THRESHOLD = 0.5


def get_profanity():
    """Lazy loader for better_profanity."""
    global _profanity_loaded
    from better_profanity import profanity

    if not _profanity_loaded:
        try:
            # better-profanity v0.7.0 uses load_censor_words
            profanity.load_censor_words(whitelist_words=TECHNICAL_WHITELIST)
            _profanity_loaded = True
        except Exception as e:
            logger.error(f"Failed to load profanity words: {e}")
    return profanity


def get_analyzer():
    """Lazy loader for Presidio AnalyzerEngine."""
    global _analyzer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine

            _analyzer = AnalyzerEngine()
        except Exception as e:
            logger.error(f"Failed to initialize Presidio for output: {e}")
    return _analyzer


@observe(name="Output Guardrails")
async def run_output_guardrails(
    answer: str, context_chunks: list[dict[str, Any]] = None
) -> GuardResult:
    """
    Checks the generated answer for PII leakage, profanity/toxicity, and hallucinations (Self-RAG).
    """
    # 1. Profanity Check
    profanity = get_profanity()
    if profanity.contains_profanity(answer):
        logger.warning(f"Profanity detected in assistant output: {answer[:50]}...")
        return GuardResult(
            passed=False,
            sanitized_content="[REDACTED TOXIC CONTENT]",
            blocked_reason="Safety violation: High toxicity detected in response.",
            metadata={"guardrail": "output_profanity"},
        )

    # 2. Self-RAG Hallucination Detection (Cost-Optimized)
    hallucination_metadata = {}
    if context_chunks:
        try:
            rag_result = await check_hallucination(answer, context_chunks)
            if not rag_result.get("passed"):
                logger.warning(
                    f"Hallucination detected! Score={rag_result.get('hallucination_score')}"
                )
                # We don't always block the response, but we add alerts/warnings
                hallucination_metadata = {
                    "hallucination_score": rag_result.get("hallucination_score"),
                    "unsupported_claims": rag_result.get("unsupported_claims"),
                    "validation_reasoning": rag_result.get("reasoning"),
                }
        except Exception as e:
            logger.error(f"Self-RAG check failed: {e}")

    # 3. PII Leak Detection
    pii_types = []
    warnings = []
    analyzer = get_analyzer()
    if analyzer:
        try:
            results = analyzer.analyze(text=answer, language="en")
            pii_types = list({res.entity_type for res in results})
            if pii_types:
                warnings.append(f"PII detected in response: {', '.join(pii_types)}")
                logger.warning(f"PII Leak detected: {pii_types}")
        except Exception as e:
            logger.error(f"PII analysis failed in output: {e}")

    # Combine warnings
    hallucination_score = hallucination_metadata.get("hallucination_score", 0.0) if hallucination_metadata else 0.0
    if hallucination_metadata:
        warnings.append(
            f"Hallucination Risk: {hallucination_score * 100:.0f}%"
        )

    # Determine overall pass/fail:
    # Fail if hallucination is above threshold (only when context was available)
    hallucination_blocked = bool(context_chunks) and hallucination_score > HALLUCINATION_BLOCK_THRESHOLD
    # Fail if high-severity PII is found in the output
    pii_blocked = bool(HIGH_SEVERITY_PII.intersection(set(pii_types)))

    output_passed = not hallucination_blocked and not pii_blocked

    blocked_reason = None
    if hallucination_blocked:
        blocked_reason = f"Hallucination detected: {hallucination_score * 100:.0f}% of response is unsupported by source documents."
        logger.warning(blocked_reason)
    elif pii_blocked:
        blocked_reason = f"High-severity PII detected in response output: {', '.join(HIGH_SEVERITY_PII.intersection(set(pii_types)))}"
        logger.warning(blocked_reason)

    return GuardResult(
        passed=output_passed,
        sanitized_content=answer if output_passed else "[RESPONSE BLOCKED: Content safety violation.]",
        blocked_reason=blocked_reason,
        pii_detected=pii_types,
        warnings=warnings,
        metadata=hallucination_metadata,
    )
