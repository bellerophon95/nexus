import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from backend.database.chat import get_message, get_messages, get_supabase
from backend.evaluation.eval_manager import EvaluationManager

logger = logging.getLogger(__name__)

router = APIRouter()


class EvalTriggerRequest(BaseModel):
    message_id: str


class GoldenDatasetRequest(BaseModel):
    message_id: str
    tier: str = "General"
    metadata: dict[str, Any] = {}


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_evaluation(request: EvalTriggerRequest) -> dict[str, Any]:
    """
    Manually triggers a full Ragas + LLM Judge evaluation for a specific message.
    """
    try:
        result = await EvaluationManager.run_manual_eval(request.message_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{message_id}")
async def get_message_evaluation_logs(message_id: str) -> list[dict[str, Any]]:
    """
    Retrieves detailed evaluation logs (reasoning, unsupported claims) for a message.
    """
    try:
        result = await asyncio.to_thread(
            lambda: (
                get_supabase()
                .table("evaluation_logs")
                .select("*")
                .eq("message_id", message_id)
                .order("created_at", desc=True)
                .execute()
            )
        )
        return result.data if result.data else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {e!s}")


@router.get("/stats")
async def get_evaluation_stats():
    """
    Returns aggregated metrics for the observability dashboard.
    """
    try:
        # Fetch last 100 evaluated messages to calculate averages
        result = await asyncio.to_thread(
            lambda: (
                get_supabase()
                .table("messages")
                .select("metrics, created_at")
                .not_.is_("metrics", "null")
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            )
        )

        messages = result.data or []
        if not messages:
            return {"avg_scores": {}, "total_evals": 0}

        sums = {}
        counts = {}

        for m in messages:
            metrics = m.get("metrics", {})
            for k, v in metrics.items():
                if isinstance(v, int | float):
                    sums[k] = sums.get(k, 0) + v
                    counts[k] = counts.get(k, 0) + 1

        avg_scores = {k: round(sums[k] / counts[k], 3) for k in sums}

        return {"avg_scores": avg_scores, "total_evals_last_100": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_evaluation_alerts(limit: int = 50):
    """
    Fetches recent threshold violations.
    """
    try:
        result = await asyncio.to_thread(
            lambda: (
                get_supabase()
                .table("eval_alerts")
                .select("*, messages(content, conversation_id)")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        )
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/golden", status_code=status.HTTP_201_CREATED)
async def promote_to_golden(request: GoldenDatasetRequest):
    """
    Adds a production message turn to the golden dataset.
    """
    try:
        msg = await get_message(request.message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        # Recover question
        history = await get_messages(msg["conversation_id"])
        question = "Unknown"
        for i, m in enumerate(history):
            if m["id"] == request.message_id and i > 0:
                question = history[i - 1]["content"]
                break

        contexts = [c.get("text", "") for c in msg.get("citations", [])]

        data = {
            "question": question,
            "ground_truth": msg["content"],
            "contexts": contexts,
            "tier": request.tier,
            "metadata": {**request.metadata, "source_message_id": request.message_id},
        }

        await asyncio.to_thread(
            lambda: get_supabase().table("eval_datasets").insert(data).execute()
        )
        return {"status": "Promoted to golden dataset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-suite")
async def run_golden_suite(background_tasks: BackgroundTasks):
    """
    Triggers a background run of the entire golden dataset.
    """
    try:
        from backend.database.chat import get_supabase
        from backend.evaluation.eval_manager import EvaluationManager

        # Fetch samples
        response = await asyncio.to_thread(
            lambda: get_supabase().table("eval_datasets").select("*").execute()
        )
        samples = response.data

        if not samples:
            return {"status": "No samples in golden dataset"}

        background_tasks.add_task(EvaluationManager.run_suite_batch, samples)
        return {
            "status": "Golden suite execution started in background",
            "sample_count": len(samples),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        # Placeholder for full suite runner
        # This would iterate over eval_datasets and trigger Evals
        # Returning status for now
        return {"status": "Golden suite run initialized in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
