import argparse
import asyncio
import json
import os
import sys
import traceback
import uuid
from typing import Any

import pandas as pd

from backend.agents.graph import nexus_graph
from backend.evaluation.llm_judge import llm_judge_evaluate_sync
from backend.evaluation.ragas_eval import run_ragas_eval_sync
from backend.observability.tracing import observe

# Thresholds
THRESHOLDS = {
    "faithfulness": 0.8,
    "answer_relevancy": 0.8,
    "context_precision": 0.7,
    "judge_correctness": 4.0,  # Out of 5
}


@observe(name="Evaluation Case")
async def run_single_test(question: str, ground_truth: str | None = None) -> dict[str, Any]:
    """
    Runs a single query through the Nexus agent graph and evaluates it.
    """
    state = {
        "messages": [],
        "current_agent": "supervisor",
        "retrieved_chunks": [],
        "iteration_count": 0,
        "max_iterations": 3,
        "validation_status": "pending",
        "hallucination_score": 0.0,
        "final_answer": "",
        "pii_detected": [],
        "query": question,
    }

    try:
        # 1. Run Pipeline
        final_state = await nexus_graph.ainvoke(state)
        answer = final_state["final_answer"]
        contexts = [c["text"] for c in final_state["retrieved_chunks"]]
        context_str = "\n".join(contexts)

        # 2. Get Trace ID
        # Since we use @observe, we can get the trace_id from langfuse
        # But in a script, it's easier to let the decorator handle it.
        # However, we need it to pass to evals.
        from langfuse.decorators import langfuse_context

        # Use child trace or unique ID
        trace_id = langfuse_context.get_current_trace_id() or str(uuid.uuid4())

        # 3. Run RAGAS Eval
        ragas_scores = run_ragas_eval_sync(
            query=question,
            answer=answer,
            contexts=contexts,
            trace_id=trace_id,
            ground_truth=ground_truth,
        )

        # 4. Run LLM Judge
        judge_scores = llm_judge_evaluate_sync(
            question=question, answer=answer, context=context_str, trace_id=trace_id
        )

        result = {
            "question": question,
            "status": "success",
            "answer": answer[:100] + "...",
            **{f"ragas_{k}": v for k, v in ragas_scores.items()},
            **{f"judge_{k}": v for k, v in judge_scores.items() if k != "reasoning"},
        }

        return result

    except Exception as e:
        traceback.print_exc()
        return {"question": question, "status": "failed", "error": str(e)}


@observe(name="Regression Suite")
async def run_regression(dataset_path: str, thresholds: dict[str, float]):
    """
    Runs the full regression suite.
    """
    print(f"🚀 Starting Regression Run: {dataset_path}")

    if not os.path.exists(dataset_path):
        print(f"❌ Error: Dataset file '{dataset_path}' not found.")
        sys.exit(1)

    with open(dataset_path) as f:
        data = json.load(f)

    results = []
    print(f"Running {len(data)} test cases...")

    for i, item in enumerate(data):
        question = item["question"]
        ground_truth = item.get("ground_truth")
        print(f"\n[{i + 1}/{len(data)}] Testing: {question}")

        res = await run_single_test(question, ground_truth)
        results.append(res)

        if res["status"] == "failed":
            print(f"   ❌ Failed: {res.get('error')}")
        else:
            print(
                "   ✅ Done. Scores: "
                + ", ".join([f"{k}: {v}" for k, v in res.items() if isinstance(v, int | float)])
            )

    # --- Summary ---
    print("\n" + "=" * 80)
    print("REGRESSION SUMMARY")
    print("=" * 80)

    df = pd.DataFrame(results)

    # Calculate means for numeric columns
    numeric_cols = [c for c in df.columns if any(m in c for m in ["ragas_", "judge_"])]
    means = df[numeric_cols].mean()

    failed_metrics = []
    for metric, threshold in thresholds.items():
        avg_val = means.get(f"ragas_{metric}") or means.get(f"judge_{metric}")
        if avg_val is not None:
            status = "✅ PASS" if avg_val >= threshold else "❌ FAIL"
            print(f"{metric:20} | Avg: {avg_val:.2f} | Threshold: {threshold:.2f} | {status}")
            if avg_val < threshold:
                failed_metrics.append(metric)
        else:
            print(f"{metric:20} | Avg: N/A  | Threshold: {threshold:.2f} | ⚠️ MISSING")

    print("=" * 80)

    if failed_metrics:
        print(
            f"\n❌ REGRESSION FAILED: The following metrics are below threshold: {', '.join(failed_metrics)}"
        )
        sys.exit(1)
    else:
        print("\n✅ REGRESSION PASSED: All metrics meet quality standards.")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/golden_dataset.json")
    parser.add_argument("--threshold-faithfulness", type=float, default=0.80)
    parser.add_argument("--threshold-relevancy", type=float, default=0.75)
    parser.add_argument("--threshold-precision", type=float, default=0.70)
    args = parser.parse_args()

    custom_thresholds = {
        "faithfulness": args.threshold_faithfulness,
        "answer_relevancy": args.threshold_relevancy,
        "context_precision": args.threshold_precision,
        "correctness": 4.0,
    }

    asyncio.run(run_regression(args.dataset, custom_thresholds))
