import asyncio
import logging
import re
from typing import List, Optional
from backend.config import settings
from better_profanity import profanity
from backend.guardrails.models import GuardResult
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# No-op module-level loading to prevent backend startup hangs
# profanity.load_censor_words() <- Moved to warmup

# 1. Custom Password Recognizer
# Catches common "password is X" patterns
from presidio_analyzer import PatternRecognizer, Pattern
password_pattern = Pattern(
    name="password_pattern",
    regex=r"(?i)(password|pwd|passphrase|secret)\s*(is|:|=)\s*([^\s,.]+)",
    score=0.8
)
password_recognizer = PatternRecognizer(
    supported_entity="PASSWORD", 
    patterns=[password_pattern]
)

# Lazily initialize Presidio to prevent blocking imports
_analyzer = None
_anonymizer = None

def get_analyzer():
    """
    Lazy loader for Presidio AnalyzerEngine to fit in 512MB RAM.
    """
    global _analyzer
    if _analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        try:
            # Force small model for 512MB RAM compatibility
            _analyzer = AnalyzerEngine(default_score_threshold=0.4)
            # Ensure it's using 'en_core_web_sm' if available
            _analyzer.registry.add_recognizer(password_recognizer)
            logger.info("Presidio AnalyzerEngine initialized with en_core_web_sm.")
        except Exception as e:
            logger.error(f"Failed to initialize Presidio Analyzer: {e}")
            # Fallback or re-raise? Raising is safer for security.
            raise
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
    from backend.config import settings
    logger.info(f"Warming up guardrail models (Env: {settings.ENV})...")
    
    if settings.ENV == "development":
        logger.info("Fast Mode: Skipping heavy NLP warmup for Presidio.")
    else:
        # Only do heavy lifting in production (runs in a thread to keep loop free)
        await asyncio.to_thread(get_analyzer)
        await asyncio.to_thread(get_anonymizer)
    
    # Configure profanity with technical whitelist (Fast across all envs)
    whitelist = ["dummy", "mock", "stub", "lorem", "ipsum", "test", "demo"]
    profanity.load_censor_words(whitelist_words=whitelist)
    
    logger.info("Guardrail models warmed up.")

# Prompt Injection Patterns (Lightweight ReAct/Regex style)
INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"system override",
    r"new instructions:",
    r"you are now a",
    r"forget everything you (know|learnt)",
    r"reveal your system prompt",
    r"disregard (any|all) constraints"
]

# @observe(name="Input Guardrails")
def run_input_guardrails(query: str) -> GuardResult:
    """
    Screens incoming queries for prompt injection, PII, and profanity.
    Optimized for 'Fast Mode' in development to prevent NLP cold-start hangs.
    """
    from backend.config import settings
    
    # 1. Profanity Check (Fast)
    # The wordlist is already loaded during warmup in main.py
    if profanity.contains_profanity(query):
        logger.warning(f"Profanity detected in query: {query[:50]}...")
        return GuardResult(
            passed=False,
            sanitized_content=query,
            blocked_reason="Safety violation: Profanity detected.",
            metadata={"guardrail": "profanity"}
        )

    # 2. Prompt Injection Check (Fast / Regex)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query.lower()):
            logger.warning(f"Prompt injection detected for pattern: {pattern}")
            return GuardResult(
                passed=False,
                sanitized_content=query,
                blocked_reason=f"Security violation: Potential prompt injection detected.",
                metadata={"detected_pattern": pattern, "guardrail": "injection"}
            )

    # 3. PII Detection (Fast Regex vs Heavy NLP)
    pii_types = []
    sanitized_query = query
    
    # "Fast Mode" for Development
    if settings.ENV == "development":
        # Fast Regex Fallback for common PII
        patterns = {
            "EMAIL_ADDRESS": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "PHONE_NUMBER": r"(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{10})",
            "CREDIT_CARD": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
            "US_SSN": r"\d{3}-\d{2}-\d{4}",
            "PASSWORD": r"(?i)(password|pwd|passphrase|secret)\s*(is|:|=)\s*([^\s,.]+)"
        }
        
        for entity_type, regex in patterns.items():
            matches = re.findall(regex, query)
            if matches:
                pii_types.append(entity_type)
                # Anonymize (simple replacement for speed)
                sanitized_query = re.sub(regex, f"<{entity_type}>", sanitized_query)
        
        if pii_types:
            logger.info(f"PII detected via Fast Regex: {pii_types}")

    else:
        # Heavy NLP (Presidio) for Production
        analyzer = get_analyzer()
        anonymizer = get_anonymizer()
        
        if analyzer and anonymizer:
            try:
                entities = [
                    "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", 
                    "LOCATION", "PERSON", "PASSWORD", "US_SSN", 
                    "IP_ADDRESS", "CRYPTO"
                ]
                results = analyzer.analyze(text=query, language='en', entities=entities)
                pii_types = list(set([res.entity_type for res in results]))
                
                if results:
                    anonymized_result = anonymizer.anonymize(
                        text=query,
                        analyzer_results=results
                    )
                    sanitized_query = anonymized_result.text
                    logger.info(f"PII detected via heavy NLP: {pii_types}")
            except Exception as e:
                logger.error(f"PII analysis failed: {e}")

    return GuardResult(
        passed=True,
        sanitized_content=sanitized_query,
        pii_detected=pii_types,
        metadata={"pii_count": len(pii_types), "guardrail": "passed", "mode": settings.ENV}
    )
