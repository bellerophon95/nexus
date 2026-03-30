import logging
from typing import List, Optional
from backend.guardrails.models import GuardResult
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Lazily initialize Presidio and Profanity to prevent blocking imports
_analyzer = None
_profanity_loaded = False

# Expanded whitelist to prevent false positives with dummy text and Markdown syntax
TECHNICAL_WHITELIST = [
    "dummy", "mock", "stub", "lorem", "ipsum", 
    "answer", "sources", "citations", "references",
    "context", "synthetic", "testing", "development"
]

def get_profanity():
    """Lazy loader for better_profanity."""
    global _profanity_loaded
    from better_profanity import profanity
    if not _profanity_loaded:
        profanity.load_censor_words(whitelist_words=TECHNICAL_WHITELIST)
        _profanity_loaded = True
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
def run_output_guardrails(answer: str) -> GuardResult:
    """
    Checks the generated answer for PII leakage and profanity/toxicity.
    """
    # 1. Profanity Check
    profanity = get_profanity()
    if profanity.contains_profanity(answer):
        logger.warning(f"Profanity detected in assistant output: {answer[:50]}...")
        return GuardResult(
            passed=False,
            sanitized_content="[REDACTED TOXIC CONTENT]",
            blocked_reason="Safety violation: High toxicity detected in response.",
            metadata={"guardrail": "output_profanity"}
        )

    # 2. PII Leak Detection
    pii_types = []
    warnings = []
    analyzer = get_analyzer()
    if analyzer:
        try:
            results = analyzer.analyze(text=answer, language='en')
            pii_types = list(set([res.entity_type for res in results]))
            if pii_types:
                warnings.append(f"PII detected in response: {', '.join(pii_types)}")
                logger.warning(f"PII Leak detected: {pii_types}")
        except Exception as e:
            logger.error(f"PII analysis failed in output: {e}")

    return GuardResult(
        passed=True,
        sanitized_content=answer,
        pii_detected=pii_types,
        warnings=warnings
    )
