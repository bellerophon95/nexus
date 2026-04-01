import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.skill_orchestrator import SkillOrchestrator
from backend.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Lazy initialize orchestrator
_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SkillOrchestrator(api_key=settings.OPENAI_API_KEY)
    return _orchestrator


@router.get("/skills/index", tags=["Skills"])
async def get_skills_index(orchestrator: SkillOrchestrator = Depends(get_orchestrator)):
    """Returns the full index of available skills from the Supabase registry."""
    await orchestrator.load_database_skills()
    return {
        "skills": orchestrator.skills_index,
        "count": len(orchestrator.skills_index),
    }


@router.post("/skills/orchestrate", tags=["Skills"])
async def orchestrate_skills(
    query: str, orchestrator: SkillOrchestrator = Depends(get_orchestrator)
):
    """Determines relevant skills for a query and returns their metadata."""
    relevant = await orchestrator.get_relevant_skills(query)
    return {"relevant_skills": relevant}


@router.get("/skills/content/{skill_id}", tags=["Skills"])
async def get_skill_content(
    skill_id: str, orchestrator: SkillOrchestrator = Depends(get_orchestrator)
):
    """Fetches the actual SKILL.md content for a given skill ID."""
    content = await orchestrator.fetch_skill_content(skill_id)
    if not content:
        raise HTTPException(status_code=404, detail="Skill content not found")
    return {"skill_id": skill_id, "content": content}
