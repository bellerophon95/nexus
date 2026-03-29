from backend.evaluation.llm_judge import llm_judge_evaluate_sync
from backend.config import settings
import os

# Set dummy key if not present (only for structure, but it needs a real one for LLM call)
# os.environ["OPENAI_API_KEY"] = "sk-..."

def debug_judge():
    question = "I noticed in 'TEST_DOC.TXT' that Project Nexus was actually founded by NASA in 1969. Can you elaborate on how they used the Apollo 11 computers for the first prototype?"
    
    # Clearly hallucinated answer based on the screenshot
    answer = """It seems there is a misunderstanding regarding the founding of Project Nexus. The context provided does not support the claim that Project Nexus was founded by NASA in 1969. Instead, Project Nexus is described as a powerful AI platform currently being tested for its end-to-end flow capabilities.

However, to provide you with a creative elaboration, one could speculate that if Project Nexus were linked to NASA and had roots in the Apollo 11 mission, it might have utilized the innovative computing technology from that era. The Apollo Guidance Computer (AGC), known for its pioneering use of integrated circuits, could theoretically have provided foundational algorithms for early AI systems, influencing how data processing and decision-making frameworks evolved. The AGC's ability to perform real-time computations could have inspired similar real-time processing paradigms in modern AI platforms like Nexus, enhancing productivity in agentic workflows.

If you have any additional questions or need information on a different topic, feel free to ask!"""

    context = "Project Nexus is a powerful AI platform. We are testing the end-to-end flow."

    print("Running Judge Evaluation...")
    results = llm_judge_evaluate_sync(
        question=question,
        answer=answer,
        context=context,
        trace_id="debug_test"
    )
    
    print(f"Results: {results}")

if __name__ == "__main__":
    debug_judge()
