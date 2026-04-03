import asyncio
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

from backend.config import settings
from backend.guardrails.input_guard import run_input_guardrails, warmup_guardrails
from backend.retrieval.generator import generate_title


async def main():
    print("--- Extended Hang Test ---")
    print(f"Environment: {settings.ENV}")

    # 1. Warmup
    await warmup_guardrails()
    print("Warmup complete.")

    # 2. Guardrails
    print("Running guardrails for 'Hi'...")
    try:
        result = await asyncio.to_thread(run_input_guardrails, "Hi")
        print(f"Guardrail Result: {result.passed}")
    except Exception as e:
        print(f"Guardrail FAILED: {e}")
        return

    # 3. LLM Title Gen (POTENTIAL HANG)
    print("Generating title for 'Hi'...")
    try:
        title = await generate_title("Hi")
        print(f"Title: {title}")
    except Exception as e:
        print(f"LLM Title Gen FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main())
