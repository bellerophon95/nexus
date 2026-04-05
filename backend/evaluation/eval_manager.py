import asyncio
import logging
import random
from typing import Any

from backend.database.chat import (
    get_message,
    save_evaluation_alert,
    save_evaluation_log,
    update_message_metrics,
)
from backend.evaluation.llm_judge import llm_judge_evaluate_async
from backend.evaluation.ragas_eval import run_ragas_eval_async

logger = logging.getLogger(__name__)

# Evaluation Thresholds for Alerting
THRESHOLDS = {
    "judge_faithfulness": 0.7,
    "judge_relevance": 0.7,
    "judge_correctness": 0.7,
    "ragas_context_precision": 0.5,
    "ragas_answer_relevancy": 0.5,
}


class EvaluationManager:
    @staticmethod
    async def run_async_eval(
        message_id: str,
        question: str,
        answer: str,
        contexts: list[str],
        trace_id: str,
        sampling_rate: float = 0.1,  # 10% for Ragas
    ):
        """
        Orchestrates background evaluations.
        Designed to be called as a FastAPI BackgroundTask.
        """
        try:
            logger.info(f"Starting async evaluation for message {message_id}")

            # 1. Run LLM Judge (Lightweight, 100% of queries)
            judge_results = await llm_judge_evaluate_async(
                question, answer, "\n".join(contexts), trace_id
            )

            # Save logs for LLM Judge
            if judge_results:
                await save_evaluation_log(
                    message_id=message_id,
                    evaluator="llm_judge",
                    scores={k: v for k, v in judge_results.items() if k != "reasoning"},
                    reasoning=judge_results.get("reasoning"),
                )

            # 2. Run Ragas (Heavyweight, sampled)
            ragas_results = {}
            if random.random() < sampling_rate:
                logger.info(f"Sampling Ragas for message {message_id}")
                ragas_results = await run_ragas_eval_async(
                    query=question, answer=answer, contexts=contexts, trace_id=trace_id
                )
                if ragas_results:
                    await save_evaluation_log(
                        message_id=message_id, evaluator="ragas", scores=ragas_results
                    )

            # 3. Update Message Metrics in DB
            msg = await get_message(message_id)
            if not msg:
                logger.error(f"Message {message_id} not found for metrics update")
                return

            current_metrics = msg.get("metrics", {})

            # Update with new scores (Prefix them for UI clarity)
            updated_metrics = {**current_metrics}
            for k, v in judge_results.items():
                if k != "reasoning":
                    metric_key = f"judge_{k}"
                    updated_metrics[metric_key] = v

                    # UI Alias Mapping & Scaling (1-5 -> 0.0-1.0)
                    if k == "relevance":
                        updated_metrics["relevanceScore"] = (v - 1) / 4.0 if v > 0 else 0.0
                    elif k == "faithfulness":
                        # Hallucination Score is inverse of Faithfulness
                        # 5/5 Faithful = 0.0 Hallucination
                        # 1/5 Faithful = 1.0 Hallucination
                        updated_metrics["hallucinationScore"] = (5 - v) / 4.0 if v > 0 else 1.0

            for k, v in ragas_results.items():
                updated_metrics[f"ragas_{k}"] = v
                # Alias Ragas answer relevancy to relevanceScore if it exists
                if k == "answer_relevancy":
                    updated_metrics["relevanceScore"] = v

            await update_message_metrics(message_id, updated_metrics)

            # 4. Check for Alerts
            for metric, score in updated_metrics.items():
                if metric in THRESHOLDS and score < THRESHOLDS[metric]:
                    logger.warning(
                        f"THRESHOLD VIOLATION: {metric} = {score} for message {message_id}"
                    )
                    await save_evaluation_alert(
                        message_id=message_id,
                        metric_name=metric,
                        value=float(score),
                        threshold=THRESHOLDS[metric],
                        comment=f"Critical drop in {metric}. Expected > {THRESHOLDS[metric]}, got {score}.",
                    )

            logger.info(f"Async evaluation complete for message {message_id}")

        except Exception as e:
            logger.error(f"EvaluationManager failed: {e}")

    @staticmethod
    async def run_suite_batch(samples: list[dict[str, Any]]):
        """
        Runs evaluation on a batch of golden dataset samples.
        """
        for sample in samples:
            try:
                # In a real scenario, we might want to Re-generate the answer
                # but for simplicity now, we evaluate the stored 'ground_truth'
                # against the same 'contexts' to see if current judge/metrics agree.
                await EvaluationManager.run_async_eval(
                    message_id=sample.get("metadata", {}).get("source_message_id", "golden_sample"),
                    question=sample["question"],
                    answer=sample["ground_truth"],
                    contexts=sample["contexts"],
                    trace_id="golden_suite_run",
                    sampling_rate=1.0,  # Run 100% for suite
                )
                # Sleep slightly to avoid rate limits
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error evaluating golden sample: {e}")

    @staticmethod
    async def run_manual_eval(message_id: str) -> dict[str, Any]:
        """
        Triggered manually by user. Runs full suite 100% including Ragas.
        """
        msg = await get_message(message_id)
        if not msg:
            return {"error": "Message not found"}

        # We need the previous user message for the question
        from backend.database.chat import get_messages

        history = await get_messages(msg["conversation_id"])

        question = "Unknown"
        for i, m in enumerate(history):
            if m["id"] == message_id and i > 0:
                question = history[i - 1]["content"]
                break

        contexts = [c.get("text", "") for c in msg.get("citations", [])]

        await EvaluationManager.run_async_eval(
            message_id=message_id,
            question=question,
            answer=msg["content"],
            contexts=contexts,
            trace_id="manual_trigger",
            sampling_rate=1.0,
        )
        return {"status": "Manual evaluation triggered"}
        # Find the question (the user message before this assistant message)
        question = "Unknown"
        for i, m in enumerate(history):
            if m["id"] == message_id and i > 0:
                # Assuming the immediate previous message is the prompt
                question = history[i - 1]["content"]
                break

        contexts = [c.get("text", "") for c in msg.get("citations", [])]

        # Run full suite (Fire and forget, but we could return immediately)
        # For manual trigger, it's safer to run it in a task and let the UI poll
        asyncio.create_task(
            EvaluationManager.run_async_eval(
                message_id=message_id,
                question=question,
                answer=msg["content"],
                contexts=contexts,
                trace_id=msg.get("trace_id") or "manual",
                sampling_rate=1.0,  # Force 100% for manual
            )
        )

        return {"status": "Evaluation triggered. Results will appear in a few seconds."}
