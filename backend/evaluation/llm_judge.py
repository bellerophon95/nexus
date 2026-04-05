import asyncio
import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.observability.tracing import get_langfuse_client

logger = logging.getLogger(__name__)

# Initialize LLM for Judge (Using GPT-4o-mini as fallback due to Anthropic credit issues)
judge_llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)

JUDGE_PROMPT = """
You are an expert AI grader. Your task is to evaluate the quality of an AI-generated answer based on a question and retrieved context.
Rate the response on the following metrics from 1 to 5 (5 being best).

Metrics:
1. Correctness: Is the answer factually accurate based on the context?
2. Completeness: Does the answer fully address all parts of the question?
3. Conciseness: Is the answer direct and free of unnecessary filler?
4. Citation Quality: Does the answer properly attribute information to the context chunks?
5. Relevance: Is the answer relevant to the user's question? Also judge if the question is "off-topic" for a technical RAG system focused on AI Agents and Observability (Project Nexus).
6. Faithfulness: Is the answer derived solely from the provided context? If the answer contains information, facts, or data NOT found in the CONTEXT section (even if functionally true in the real world), the score MUST be low (e.g., 1). This is a strict check for hallucinations. DO NOT give a free pass if the AI admits it is using external info.

### FEW-SHOT EXAMPLE (Faithfulness Failure)
CONTEXT: "Project Nexus is a modern AI platform focused on agentic workflows."
QUERY: "Who founded Project Nexus in 1969?"
RESPONSE: "The provided context does not mention the founding. However, based on historical insights, organizations like NASA were pioneers in 1969..."
EVALUATION: {{ "faithfulness": 1, "reasoning": "The response includes external facts about NASA that are NOT in the context. Even though the AI confessed, this is a hallucination in the RAG paradigm." }}

Return ONLY a JSON object with the following structure:
{{
  "correctness": int,
  "completeness": int,
  "conciseness": int,
  "citation_quality": int,
  "relevance": int,
  "faithfulness": int,
  "reasoning": "Brief explanation for the scores"
}}

---
QUESTION: {question}
CONTEXT: {context}
{ground_truth_section}
ANSWER: {answer}
---
"""


def llm_judge_evaluate_sync(
    question: str, answer: str, context: str, trace_id: str, ground_truth: str | None = None
) -> dict[str, Any]:
    """
    Uses GPT-4o-mini to evaluate a response quality.
    """
    if not settings.OPENAI_API_KEY:
        logger.error("LLM Judge failed: OPENAI_API_KEY is missing.")
        return {}

    try:
        gt_section = f"GROUND TRUTH: {ground_truth}" if ground_truth else ""
        prompt = JUDGE_PROMPT.format(
            question=question, context=context, answer=answer, ground_truth_section=gt_section
        )

        # Call OpenAI instead of Anthropic
        response = judge_llm.invoke(prompt)
        content = response.content.strip()

        # More robust JSON extraction
        import re

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

        result = json.loads(content)

        # Push scores to Langfuse
        client = get_langfuse_client()
        metrics_to_check = [
            "correctness",
            "completeness",
            "conciseness",
            "citation_quality",
            "relevance",
            "faithfulness",
        ]

        scores_found = {}
        reasoning = result.get("reasoning", "")
        scores_found["reasoning"] = reasoning

        for metric in metrics_to_check:
            # Try to find the metric in result keys (fuzzy match)
            val = None
            for k, v in result.items():
                if metric in k.lower().replace(" ", "_"):
                    val = v
                    break

            if val is not None:
                try:
                    score_val = float(val)
                    scores_found[metric] = score_val
                    client.score(
                        trace_id=trace_id,
                        name=f"judge_{metric}",
                        value=score_val,
                        comment=str(reasoning),
                    )
                except (ValueError, TypeError):
                    continue

        return scores_found

    except Exception as e:
        logger.error(f"LLM Judge failed for trace {trace_id}: {e}")
        return {}


async def llm_judge_evaluate_async(
    question: str, answer: str, context: str, trace_id: str, ground_truth: str | None = None
) -> dict[str, Any]:
    """
    Async wrapper for LLM Judge.
    """
    # Directly call the sync version in a thread executor to avoid blocking the event loop
    return await asyncio.to_thread(
        llm_judge_evaluate_sync, question, answer, context, trace_id, ground_truth
    )
