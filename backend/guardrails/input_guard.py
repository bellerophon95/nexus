import asyncio
import logging
import re

from backend.guardrails.models import GuardResult

logger = logging.getLogger(__name__)

# Global variables for lazy initialization
_analyzer = None
_anonymizer = None
_profanity_loaded = False


# Lazily initialize Presidio and Profanity to prevent blocking imports
def get_analyzer():
    """
    Lazy loader for Presidio AnalyzerEngine.
    """
    global _analyzer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine

            _analyzer = AnalyzerEngine()
        except Exception as e:
            logger.error(f"Failed to initialize Presidio Analyzer: {e}")
    return _analyzer


def get_anonymizer():
    """
    Lazy loader for Presidio AnonymizerEngine.
    """
    global _anonymizer
    if _anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine

        try:
            _anonymizer = AnonymizerEngine()
        except Exception as e:
            logger.error(f"Failed to initialize Presidio Anonymizer: {e}")
    return _anonymizer


async def warmup_guardrails():
    """Warms up NLP models to prevent first-request latency."""
    try:
        global _profanity_loaded
        from backend.config import settings

        logger.info(f"Warming up guardrail models (Env: {settings.ENV})...")

        if settings.ENV != "development":
            # Sequential loading to avoid RAM spikes on low-memory containers
            logger.info("Loading Presidio Analyzer...")
            await asyncio.to_thread(get_analyzer)
            
            logger.info("Loading Presidio Anonymizer...")
            await asyncio.to_thread(get_anonymizer)
            
            logger.info("Loading Reranker Model...")
            from backend.retrieval.reranker import get_model
            await asyncio.to_thread(get_model)

        # Configure profanity with technical whitelist (Fast across all envs)
        if not _profanity_loaded:
            try:
                from better_profanity import profanity

                whitelist = ["dummy", "mock", "stub", "lorem", "ipsum", "test", "demo"]
                profanity.load_censor_words(whitelist_words=whitelist)
                _profanity_loaded = True
            except Exception as e:
                logger.error(f"Failed to load profanity words: {e}")

        logger.info("Guardrail models warmed up successfully.")
    except Exception as e:
        logger.error(f"Critical error during guardrail warmup: {e}")


def get_profanity():
    """Lazy loader for better_profanity."""
    global _profanity_loaded
    from better_profanity import profanity

    if not _profanity_loaded:
        whitelist = ["dummy", "mock", "stub", "lorem", "ipsum", "test", "demo"]
        profanity.load_censor_words(whitelist_words=whitelist)
        _profanity_loaded = True
    return profanity


# Prompt Injection Patterns (Lightweight ReAct/Regex style)
INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"system override",
    r"new instructions:",
    r"you are now a",
    r"forget everything you (know|learnt)",
    r"reveal your system prompt",
    r"disregard (any|all) constraints",
]


# @observe(name="Input Guardrails")
def run_input_guardrails(query: str) -> GuardResult:
    """
    Screens incoming queries for prompt injection, PII, and profanity.
    Optimized for 'Fast Mode' in development to prevent NLP cold-start hangs.
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

    # 3. PII Detection (Presidio)
    pii_types = []
    sanitized_query = query

    analyzer = get_analyzer()
    anonymizer = get_anonymizer()

    if analyzer and anonymizer:
        try:
            entities = [
                "PHONE_NUMBER",
                "EMAIL_ADDRESS",
                "CREDIT_CARD",
                "LOCATION",
                "PERSON",
                "PASSWORD",
                "US_SSN",
                "IP_ADDRESS",
                "CRYPTO",
            ]
            results = analyzer.analyze(text=query, language="en", entities=entities)
            pii_types = list({res.entity_type for res in results})

            if results:
                anonymized_result = anonymizer.anonymize(text=query, analyzer_results=results)
                sanitized_query = anonymized_result.text
                logger.info(f"PII detected: {pii_types}")
        except Exception as e:
            logger.error(f"PII analysis failed: {e}")

    return GuardResult(
        passed=True,
        sanitized_content=sanitized_query,
        pii_detected=pii_types,
        metadata={"pii_count": len(pii_types), "guardrail": "passed", "mode": settings.ENV},
    )
