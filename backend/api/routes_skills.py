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


@router.get("/index", tags=["Skills"])
async def get_skills_index(orchestrator: SkillOrchestrator = Depends(get_orchestrator)):
    """Returns the full index of available skills and pre-configured bundles from Qdrant."""
    skills = await orchestrator.fetch_skill_manifests()

    # Define strategic bundles for the UI
    bundles = {
        "Deep Research": ["researcher", "financial_analyst"],
        "Production Readiness": ["agent_code_quality", "researcher"],
        "Financial Expert": ["financial_analyst"],
    }

    return {
        "skills": skills,
        "bundles": bundles,
        "count": len(skills),
    }


@router.post("/orchestrate", tags=["Skills"])
async def orchestrate_skills(
    query: str, orchestrator: SkillOrchestrator = Depends(get_orchestrator)
):
    """Performs semantic 'Radial Discovery' for a query and returns relevant expert roles."""
    relevant = await orchestrator.get_relevant_skills(query)
    return {"relevant_skills": relevant}


@router.get("/content/{skill_id}", tags=["Skills"])
async def get_skill_content(
    skill_id: str, orchestrator: SkillOrchestrator = Depends(get_orchestrator)
):
    """Fetches the actual instruction set (payload) for a given skill ID from Qdrant."""
    skill = await orchestrator.get_skill_by_id(skill_id)
    if not skill or "content" not in skill:
        raise HTTPException(
            status_code=404, detail=f"Skill '{skill_id}' content not found in vector index"
        )

    return {
        "skill_id": skill_id,
        "content": skill["content"],
        "meta": {k: v for k, v in skill.items() if k != "content"},
    }
