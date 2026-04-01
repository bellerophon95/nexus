import asyncio
import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    """
    Manages the orchestration of local 'Nexus Skills'.
    Uses a filesystem-based strategy to inject only relevant skills into the agent context.
    """

    SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
    REGISTRY_PATH = os.path.join(SKILLS_DIR, "registry.json")

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.skills_index: list[dict] = []
        self.last_load = 0
        self._load_lock = asyncio.Lock()

    async def load_local_skills(self):
        """Loads the latest skills index from the local registry."""
        async with self._load_lock:
            # Simple caching mechanism for the local filesystem (re-scan only if registry changed or manually triggered)
            # For now, we'll reload it every time for ease of development during this migration.
            try:
                if os.path.exists(self.REGISTRY_PATH):
                    with open(self.REGISTRY_PATH) as f:
                        self.skills_index = json.load(f)
                    logger.info(f"Loaded {len(self.skills_index)} local skills from registry.")
                else:
                    logger.warning(f"Skill registry not found at {self.REGISTRY_PATH}")
                    self.skills_index = []
            except Exception as e:
                logger.error(f"Failed to load local skill manifests: {e}")
                self.skills_index = []

    async def get_relevant_skills(self, query: str, top_k: int = 3) -> list[dict]:
        """Uses LLM to select the most relevant skills for a given query."""
        await self.load_local_skills()

        if not self.skills_index:
            return []

        # Prepare a list of candidates including the new role/expertise metadata
        candidate_list = []
        for s in self.skills_index:
            meta = s.get("metadata", {})
            candidate_list.append(
                {
                    "id": s["id"],
                    "role": meta.get("role", "General Analyst"),
                    "name": meta.get("name", s["id"]),
                    "description": meta.get("description", ""),
                    "expertise": meta.get("expertise", []),
                }
            )

        prompt = f"""
        Given the user query: "{query}"

        Identify the top {top_k} most relevant expert skill roles from the following list.
        Each role has specific expertise and instructions.
        
        Return ONLY a JSON list of skill IDs.

        Available Skills:
        {json.dumps(candidate_list, indent=2)}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are the Nexus Skill Orchestrator. Select the best expert roles for the task.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            selected_ids = (
                result.get("selected_ids", []) or result.get("skills", []) or result.get("ids", [])
            )

            # Map IDs back to full skill objects
            relevant = [s for s in self.skills_index if s["id"] in selected_ids]
            return relevant[:top_k]

        except Exception as e:
            logger.error(f"Error orchestrating skills: {e}")
            return []

    async def fetch_skill_content(self, skill_id: str) -> str | None:
        """Fetches the actual SKILL.md content from the local filesystem."""
        skill = next((s for s in self.skills_index if s["id"] == skill_id), None)
        if not skill:
            return None

        # Determine path to SKILL.md
        skill_dir = os.path.join(self.SKILLS_DIR, skill_id)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")

        try:
            if os.path.exists(skill_md_path):
                with open(skill_md_path) as f:
                    return f.read()
            else:
                logger.warning(f"SKILL.md not found for {skill_id} at {skill_md_path}")
        except Exception as e:
            logger.error(f"Failed to read SKILL.md for skill {skill_id}: {e}")
        return None

    async def get_orchestration_prompt(self, query: str) -> str:
        """Generates a combined prompt block containing relevant skills and their roles."""
        relevant_skills = await self.get_relevant_skills(query)
        if not relevant_skills:
            return ""

        prompt_parts = ["\n### SPECIALIZED SKILLS & EXPERT ROLES INJECTED\n"]

        tasks = [self.fetch_skill_content(s["id"]) for s in relevant_skills]
        contents = await asyncio.gather(*tasks)

        for skill, content in zip(relevant_skills, contents, strict=True):
            if content:
                role = skill.get("metadata", {}).get("role", "Expert Analyst")
                expertise = ", ".join(skill.get("metadata", {}).get("expertise", []))

                parts = [
                    f"#### [Agent: {role}]",
                    f"**Expertise**: {expertise}" if expertise else "",
                    content,
                    "---",
                ]
                prompt_parts.append("\n".join([p for p in parts if p]))

        return "\n".join(prompt_parts)
