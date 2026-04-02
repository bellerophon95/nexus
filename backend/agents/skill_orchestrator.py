import asyncio
import json
import logging
import os

from openai import AsyncOpenAI

from backend.database.supabase import get_async_supabase

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    """
    Manages the orchestration of 'Nexus Skills' from Supabase.
    Uses a database-driven strategy to inject only relevant expert roles into the agent context.
    """

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.skills_index: list[dict] = []
        self._load_lock = asyncio.Lock()

    async def load_database_skills(self):
        """Loads the latest skills index by merging local and database registries."""
        async with self._load_lock:
            # 1. Initial load from local registry (Standard Skills)
            self._load_local_registry()
            local_count = len(self.skills_index)

            # 2. Re-fetch from Supabase to augment with dynamic skills
            try:
                supabase = await get_async_supabase()
                response = await supabase.table("skills").select("*").execute()

                if response.data:
                    # Merge by ID, database takes precedence for matching IDs
                    remote_skills = {s["id"]: s for s in response.data}
                    local_skills = {s["id"]: s for s in self.skills_index}

                    merged = {**local_skills, **remote_skills}
                    self.skills_index = list(merged.values())
                    logger.info(
                        f"Loaded {len(self.skills_index)} expert skills ({local_count} local, {len(remote_skills)} remote)."
                    )
                else:
                    logger.warning("Supabase skill registry empty. Using only local definitions.")

            except Exception as e:
                logger.error(f"Failed to load database skill manifests: {e}. Using local fallback.")

    def _load_local_registry(self):
        """Loads skills from the local registry.json file as a fallback."""
        try:
            registry_path = os.path.join("backend", "skills", "registry.json")
            if os.path.exists(registry_path):
                with open(registry_path) as f:
                    data = json.load(f)
                    # Flatten local registry format to match Supabase schema
                    self.skills_index = []
                    for item in data:
                        skill = {"id": item["id"]}
                        skill.update(item.get("metadata", {}))
                        self.skills_index.append(skill)
                logger.info(f"Loaded {len(self.skills_index)} expert skills from local registry.")
            else:
                logger.error(f"Local registry not found at {registry_path}")
                self.skills_index = []
        except Exception as e:
            logger.error(f"Failed to load local skill registry: {e}")
            self.skills_index = []

    async def get_relevant_skills(self, query: str, top_k: int = 3) -> list[dict]:
        """Uses LLM to select the most relevant skills for a given query."""
        await self.load_database_skills()

        if not self.skills_index:
            return []

        # Prepare a list of candidates including the database-backed role/expertise metadata
        candidate_list = []
        for s in self.skills_index:
            candidate_list.append(
                {
                    "id": s["id"],
                    "role": s.get("role", "General Analyst"),
                    "name": s.get("name", s["id"]),
                    "description": s.get("description", ""),
                    "expertise": s.get("expertise", []),
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
        """Fetches the actual skill instructions (content) from the database."""
        skill = next((s for s in self.skills_index if s["id"] == skill_id), None)
        if not skill:
            return None

        # Content is already part of the initial fetch in this version.
        # If skills grow very large, we can optimize this to only fetch content on-demand.
        return skill.get("content")

    async def get_orchestration_prompt(self, query: str) -> str:
        """Generates a combined prompt block containing relevant skills from Supabase."""
        relevant_skills = await self.get_relevant_skills(query)
        if not relevant_skills:
            return ""

        prompt_parts = ["\n### SPECIALIZED SKILLS & EXPERT ROLES INJECTED\n"]

        # In this version, content is already pre-loaded in load_database_skills
        for skill in relevant_skills:
            content = skill.get("content")
            if content:
                role = skill.get("role", "Expert Analyst")
                expertise = ", ".join(skill.get("expertise", []))

                parts = [
                    f"#### [Agent: {role}]",
                    f"**Expertise**: {expertise}" if expertise else "",
                    content,
                    "---",
                ]
                prompt_parts.append("\n".join([p for p in parts if p]))

        return "\n".join(prompt_parts)
