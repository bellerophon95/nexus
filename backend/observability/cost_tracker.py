import logging

from backend.observability.tracing import get_langfuse_client

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (USD)
PRICING = {
    "gpt-4o-mini": {"prompt": 0.150, "completion": 0.600},
    "claude-3-haiku": {"prompt": 0.250, "completion": 1.250},
    "text-embedding-3-small": {"prompt": 0.020, "completion": 0.0},
}


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int = 0) -> float:
    """
    Calculates the USD cost of an LLM call based on token counts.
    """
    if model_name not in PRICING:
        logger.warning(f"Cost tracking not supported for model: {model_name}")
        return 0.0

    price = PRICING[model_name]
    cost = (prompt_tokens / 1_000_000 * price["prompt"]) + (
        completion_tokens / 1_000_000 * price["completion"]
    )
    return cost


def score_cost(trace_id: str, cost: float):
    """
    Pushes total cost metadata to Langfuse trace as a score.
    """
    try:
        if not trace_id:
            return

        client = get_langfuse_client()
        client.score(
            trace_id=trace_id, name="total_cost_usd", value=cost, comment="Automated cost tracking"
        )
    except Exception as e:
        logger.error(f"Failed to score cost in Langfuse: {e}")
