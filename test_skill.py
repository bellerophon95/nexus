import asyncio

from backend.agents.skill_orchestrator import SkillOrchestrator
from backend.config import settings


async def main():
    orc = SkillOrchestrator(api_key=settings.OPENAI_API_KEY)
    skills = await orc.get_relevant_skills("How do you conduct balance sheet analyses")
    print("Relevant skills:", skills)

    prompt = await orc.get_orchestration_prompt("How do you conduct balance sheet analyses")
    print(f"Orchestration Prompt Length: {len(prompt)}")
    print(f"Prompt content:\n{prompt}")


if __name__ == "__main__":
    asyncio.run(main())
