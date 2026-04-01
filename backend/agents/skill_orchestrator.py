import json
import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)

class SkillOrchestrator:
    """
    Manages the orchestration of 'antigravity-awesome-skills'.
    Uses a lazy-loading strategy to inject only relevant skills into the agent context.
    """
    
    BASE_URL = "https://raw.githubusercontent.com/sickn33/antigravity-awesome-skills/main"
    INDEX_PATH = "/data/skills_index.json"
    BUNDLES_PATH = "/data/bundles.json"
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.skills_index: List[Dict] = []
        self.bundles: Dict[str, List[str]] = {}
        self.last_sync = 0
        self._sync_lock = asyncio.Lock()

    async def sync_manifests(self):
        """Fetches the latest skills index and bundles from GitHub."""
        async with self._sync_lock:
            # Simple caching for 1 hour
            import time
            if time.time() - self.last_sync < 3600 and self.skills_index:
                return

            try:
                async with httpx.AsyncClient() as client:
                    index_resp = await client.get(f"{self.BASE_URL}{self.INDEX_PATH}")
                    bundles_resp = await client.get(f"{self.BASE_URL}{self.BUNDLES_PATH}")
                    
                    if index_resp.status_code == 200:
                        self.skills_index = index_resp.json()
                    if bundles_resp.status_code == 200:
                        self.bundles = bundles_resp.json()
                        
                    self.last_sync = time.time()
                    logger.info(f"Synced {len(self.skills_index)} skills and {len(self.bundles)} bundles.")
            except Exception as e:
                logger.error(f"Failed to sync skill manifests: {e}")

    async def get_relevant_skills(self, query: str, top_k: int = 3) -> List[Dict]:
        """Uses LLM to select the most relevant skills for a given query."""
        await self.sync_manifests()
        
        if not self.skills_index:
            return []

        # Prepare a shortened list for the LLM to choose from (ID and Description)
        # In a real production scenario with 1,300+ skills, we would use vector search here.
        # For Nexus, we filter by category or use a subset of popular skills first.
        
        candidate_list = [
            {"id": s["id"], "name": s["metadata"].get("name", s["id"]), "description": s["metadata"].get("description", "")}
            for s in self.skills_index[:100] # Limiting to top 100 for token efficiency in this first version
        ]

        prompt = f"""
        Given the user query: "{query}"
        
        Identify the top {top_k} most relevant skills from the following list that would help an AI agent answer this query accurately.
        Return ONLY a JSON list of skill IDs.
        
        Available Skills:
        {json.dumps(candidate_list, indent=2)}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a Skill Orchestrator for an AI agent."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            selected_ids = result.get("selected_ids", []) or result.get("skills", [])
            
            # Map IDs back to full skill objects
            relevant = [s for s in self.skills_index if s["id"] in selected_ids]
            return relevant[:top_k]
            
        except Exception as e:
            logger.error(f"Error orchestrating skills: {e}")
            return []

    async def fetch_skill_content(self, skill_id: str) -> Optional[str]:
        """Fetches the actual SKILL.md content for a specific skill."""
        skill = next((s for s in self.skills_index if s["id"] == skill_id), None)
        if not skill:
            return None
            
        path = skill.get("path", f"skills/{skill_id}")
        url = f"{self.BASE_URL}/{path}/SKILL.md"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
        except Exception as e:
            logger.error(f"Failed to fetch content for skill {skill_id}: {e}")
        return None

    async def get_orchestration_prompt(self, query: str) -> str:
        """Generates a combined prompt block containing relevant skills."""
        relevant_skills = await self.get_relevant_skills(query)
        if not relevant_skills:
            return ""

        prompt_parts = ["\n### RELEVANT SKILLS INJECTED\n"]
        
        tasks = [self.fetch_skill_content(s["id"]) for s in relevant_skills]
        contents = await asyncio.gather(*tasks)
        
        for skill, content in zip(relevant_skills, contents):
            if content:
                prompt_parts.append(f"#### Skill: {skill['id']}\n{content}\n")
        
        return "\n".join(prompt_parts)
