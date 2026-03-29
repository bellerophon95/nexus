import asyncio
import logging
from typing import List, Dict, Any, Optional
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from backend.config import settings
from backend.observability.tracing import get_langfuse_client

logger = logging.getLogger(__name__)

def run_ragas_eval_sync(
    query: str, 
    answer: str, 
    contexts: List[str], 
    trace_id: str,
    ground_truth: Optional[str] = None
) -> Dict[str, float]:
    """
    Runs RAGAS evaluation and pushes scores to Langfuse.
    """
    try:
        if not settings.OPENAI_API_KEY:
            logger.error("RAGAS Evaluation failed: OPENAI_API_KEY is missing.")
            return {}

        # Prepare dataset for RAGAS
        data = {
            "question": [query],
            "answer": [answer],
            "contexts": [contexts]
        }
        
        metrics = [faithfulness, answer_relevancy, context_precision]
        
        if ground_truth:
            data["ground_truth"] = [ground_truth]
            metrics.append(context_recall)

        # Prep metrics with explicit LLM and Embeddings to avoid version conflicts
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        eval_llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
        eval_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.OPENAI_API_KEY)
        
        # We need to wrap metrics if using custom LLM in some ragas versions, 
        # but usually passing them to evaluate() is enough in 0.1.x+
        
        dataset = Dataset.from_dict(data)
        
        # Run evaluation
        result = evaluate(
            dataset,
            metrics=metrics,
            llm=eval_llm,
            embeddings=eval_embeddings
        )
        
        # Convert to dict
        eval_dict = result.to_pandas().iloc[0].to_dict()
        logger.info(f"RAGAS Eval complete for trace {trace_id}: {eval_dict}")
        
        # Push to Langfuse
        client = get_langfuse_client()
        scores = {}
        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            if metric in eval_dict and eval_dict[metric] is not None:
                val = float(eval_dict[metric])
                scores[metric] = val
                client.score(
                    trace_id=trace_id,
                    name=f"ragas_{metric}",
                    value=val
                )
        
        return scores
            
    except Exception as e:
        logger.error(f"RAGAS evaluation failed for trace {trace_id}: {e}")
        return {}

async def run_ragas_eval_async(
    query: str, 
    answer: str, 
    contexts: List[str], 
    trace_id: str,
    ground_truth: Optional[str] = None
):
    """
    Async wrapper for RAGAS eval.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        run_ragas_eval_sync, 
        query, 
        answer, 
        contexts, 
        trace_id,
        ground_truth
    )
