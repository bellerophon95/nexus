import asyncio
import json
import os
import sys
import time
from typing import Any

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from backend.agents.graph import nexus_graph
from backend.evaluation.llm_judge import llm_judge_evaluate_async

# ANSI colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def run_eval_sample(sample: dict[str, Any]) -> dict[str, Any]:
    question = sample["question"]
    ground_truth = sample.get("ground_truth", "")
    tier = sample.get("tier", "Unknown")

    print(f"{BOLD}[Testing]{RESET} Tier: {tier} | Question: {question[:60]}...")

    start_time = time.perf_counter()

    # 1. Run the RAG Graph
    initial_state = {
        "messages": [],
        "query": question,
        "current_agent": "supervisor",
        "retrieved_chunks": [],
        "iteration_count": 0,
        "max_iterations": 3,
        "search_count": 0,
        "validation_status": "pending",
        "final_answer": "",
        "activity_log": [],
        "user_id": "00000000-0000-0000-0000-000000000000",
        "match_threshold": 0.2,
        "rerank": True,
    }

    try:
        final_state = await nexus_graph.ainvoke(initial_state)
        answer = final_state.get("final_answer", "")
        chunks = final_state.get("retrieved_chunks", [])
        context = "\n".join([c.get("text", "") for c in chunks])

        latency = (time.perf_counter() - start_time) * 1000

        # 2. Judge the result
        judge_results = await llm_judge_evaluate_async(
            question=question,
            answer=answer,
            context=context,
            trace_id=f"ci-eval-{int(time.time())}",
            ground_truth=ground_truth,
        )

        return {
            "question": question,
            "answer": answer,
            "latency_ms": latency,
            "scores": judge_results,
            "passed": judge_results.get("correctness", 0) >= 4
            and judge_results.get("faithfulness", 0) >= 3,
        }

    except Exception as e:
        print(f"{RED}Error processing sample: {e}{RESET}")
        return {"question": question, "error": str(e), "passed": False}


async def main():
    dataset_path = "evals/golden_dataset.json"
    if not os.path.exists(dataset_path):
        print(f"{RED}Error: Dataset not found at {dataset_path}{RESET}")
        sys.exit(1)

    with open(dataset_path) as f:
        dataset = json.load(f)

    print(f"\n{BOLD}🚀 Starting Automated Regression Suite ({len(dataset)} samples){RESET}\n")

    results = []
    for sample in dataset:
        res = await run_eval_sample(sample)
        results.append(res)

        if res.get("passed"):
            print(
                f"  {GREEN}✅ PASSED{RESET} | Correctness: {res['scores'].get('correctness')}/5 | Latency: {res['latency_ms']:.0f}ms"
            )
        else:
            if "error" in res:
                print(f"  {RED}❌ FAILED{RESET} | Error: {res['error']}")
            else:
                print(
                    f"  {RED}❌ FAILED{RESET} | Correctness: {res['scores'].get('correctness')}/5 | Reasoning: {res['scores'].get('reasoning')}"
                )

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    avg_correctness = (
        sum(r.get("scores", {}).get("correctness", 0) for r in results) / total if total > 0 else 0
    )
    avg_latency = sum(r.get("latency_ms", 0) for r in results) / total if total > 0 else 0

    print(f"\n{BOLD}📊 Evaluation Summary{RESET}")
    print(f"  Total Samples: {total}")
    print(f"  Passed: {passed}/{total} ({(passed/total)*100:.1f}%)")
    print(f"  Avg Correctness: {avg_correctness:.2f}/5")
    print(f"  Avg Latency: {avg_latency:.0f}ms")

    if passed < total * 0.8:  # Fail if less than 80% pass
        print(f"\n{RED}{BOLD}❌ REGRESSION DETECTED: Success rate too low!{RESET}")
        sys.exit(1)

    print(f"\n{GREEN}{BOLD}✨ All critical tests passed!{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
