import asyncio

from backend.agents.skill_orchestrator import SkillOrchestrator
from backend.config import settings
from backend.retrieval.generator import generate_answer


async def main():
    orc = SkillOrchestrator(api_key=settings.OPENAI_API_KEY)
    prompt = await orc.get_orchestration_prompt("How do you conduct balance sheet analyses")
    answer = await generate_answer("How do you conduct balance sheet analyses", [], None, prompt)
    print("OUTPUT:\n", answer)


if __name__ == "__main__":
    asyncio.run(main())
