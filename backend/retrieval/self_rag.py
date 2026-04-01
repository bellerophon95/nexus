import json
import logging
from typing import Any

from openai import OpenAI
from backend.config import settings
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Initialize client lazily
_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client

SELF_RAG_PROMPT = """You are a Fact-Checking Validator for a RAG system.
Your task is to verify if the provided Answer is strictly grounded in the retrieved Context.

### CONTEXT:
{context}

### ANSWER:
{answer}

### INSTRUCTIONS:
1. Identify all factual claims in the Answer.
2. For each claim, check if it is supported by the Context.
3. Provide a JSON response with the following structure:
{{
    "passed": boolean,
    "hallucination_score": float (0.0 to 1.0, where 1.0 is full hallucination),
    "unsupported_claims": ["list", "of", "claims", "not", "supported", "by", "context"],
    "reasoning": "brief explanation of your findings"
}}

If a claim is partially supported, mark it as unsupported if identifying details (dates, numbers, names) are missing or incorrect.
Be strict. If the context is silent on a claim, it is a hallucination.
"""

@observe(name="Self-RAG Validation")
async def check_hallucination(answer: str, context_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Validates the generated answer against retrieved context using gpt-4o-mini.
    """
    if not context_chunks:
        return {
            "passed": False,
            "hallucination_score": 1.0,
            "unsupported_claims": ["No context provided for validation"],
            "reasoning": "Validation failed because no context was available to verify the answer."
        }

    # Format context for the prompt
    context_text = "\n\n".join([f"Chunk {i+1}: {c.get('text', '')}" for i, c in enumerate(context_chunks)])
    
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise fact-checker. Respond only in JSON."},
                {"role": "user", "content": SELF_RAG_PROMPT.format(context=context_text, answer=answer)}
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        
        result = json.loads(response.choices[0].message.content)
        logger.info(f"Self-RAG Result: Passed={result.get('passed')} Score={result.get('hallucination_score')}")
        return result
        
    except Exception as e:
        logger.error(f"Self-RAG validation failed: {e}")
        # Default to passing if validation itself fails, to avoid blocking the user
        return {
            "passed": True, 
            "hallucination_score": 0.0, 
            "unsupported_claims": [], 
            "reasoning": f"Validation technical error: {e}"
        }
