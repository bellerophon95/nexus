import logging
import os
from typing import Any

from openai import AsyncOpenAI
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    """
    Manages the orchestration of 'Nexus Skills' using Qdrant Vector Search.
    Enables 'Radial Discovery' by finding semantically relevant expertise for any query.
    """

    def __init__(self, api_key: str):
        self.openai_client = AsyncOpenAI(api_key=api_key)

        # Load Qdrant credentials from environment
        qdrant_url = os.environ.get(
            "QDRANT_URL",
            "https://8d7a6e9f-b393-4cf1-9138-d041cff24fe4.us-west-1-0.aws.cloud.qdrant.io:6333",
        )
        qdrant_api_key = os.environ.get(
            "QDRANT_API_KEY",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZDE5ZTI3NGEtOGI5NC00ZjY4LThjYWYtMmVkZTdiZmY1MDk3In0.92EUv4QVebX6-qjc_7VnIe7G_MahexsbDyUa9W5eheE",
        )

        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = "nexus_skills"

    async def get_embedding(self, text: str) -> list[float]:
        """Generates a semantic vector for the query."""
        resp = await self.openai_client.embeddings.create(
            input=text, model="text-embedding-3-small"
        )
        return resp.data[0].embedding

    async def get_relevant_skills(self, query: str, top_k: int = 2) -> list[dict[str, Any]]:
        """
        Performs high-speed Radial Discovery using semantic vector search.
        Identified skills are injected into the agent's reasoning loop.
        """
        try:
            query_vector = await self.get_embedding(query)

            # Search Qdrant for semantically similar skill roles/descriptions
            search_result = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=0.35,  # Ensure relevance
            ).points

            relevant_skills = []
            for hit in search_result:
                skill_data = hit.payload
                skill_data["match_score"] = hit.score
                relevant_skills.append(skill_data)

            if relevant_skills:
                logger.info(
                    f"Radial Discovery matched {len(relevant_skills)} experts for: '{query[:50]}...'"
                )

            return relevant_skills

        except Exception as e:
            logger.error(f"Radial Discovery failed: {e}")
            return []

    async def get_orchestration_prompt(self, query: str) -> str:
        """
        Generates the 'Expert Injection' block for the system prompt.
        Lazy-routes the most relevant skill instructions into the active context.
        """
        relevant_skills = await self.get_relevant_skills(query)
        if not relevant_skills:
            return ""

        prompt_parts = ["\n### ⚡ NEXUS EXPERT ORCHESTRATION: RADIAL DISCOVERY ACTIVE\n"]
        prompt_parts.append(
            "CRITICAL OVERRIDE: The following specialized expert roles have been dynamically injected based on the user's intent. YOU MUST BEGIN your response by introducing yourself as this expert persona. YOU MUST COMPLETELY ADOPT THEIR PERSONA, TONE, AND EXPERTISE. Do NOT drop character. You are no longer a general assistant—you are exactly this expert.\n"
        )

        for skill in relevant_skills:
            role = skill.get("role", "Expert Consultant")
            name = skill.get("name", "Specialized Agent")
            expertise = ", ".join(skill.get("expertise", []))
            content = skill.get("content", "")

            parts = [
                f"#### [Agent: {name} | Role: {role}]",
                f"**Technical Expertise**: {expertise}" if expertise else "",
                "**Expert Instructions**:",
                content,
                "\n---",
            ]
            prompt_parts.append("\n".join([p for p in parts if p]))

        return "\n".join(prompt_parts)

    async def get_skill_by_id(self, skill_id: str) -> dict[str, Any] | None:
        """Directly retrieves a specific skill's instructions/payload by its unique ID."""
        try:
            # We use name-based UUIDs for stable lookups.
            import uuid

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"nexus.skills.{skill_id}"))

            result = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )

            if result:
                return result[0].payload
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve skill {skill_id}: {e}")
            return None

    async def fetch_skill_manifests(self) -> list[dict[str, Any]]:
        """Used by the UI to list all available capabilities in the Nexus Skill Hub."""
        try:
            # Scroll through existing skills (up to 100 for now)
            points, _ = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            return [p.payload for p in points]
        except Exception as e:
            logger.error(f"Failed to fetch skill manifests for UI: {e}")
            return []
