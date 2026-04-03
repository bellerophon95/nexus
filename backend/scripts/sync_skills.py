import asyncio
import json
import os
import re
import logging
import uuid
from typing import List, Dict, Any

import openai
from qdrant_client import QdrantClient, models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
QDRANT_URL = "https://8d7a6e9f-b393-4cf1-9138-d041cff24fe4.us-west-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZDE5ZTI3NGEtOGI5NC00ZjY4LThjYWYtMmVkZTdiZmY1MDk3In0.92EUv4QVebX6-qjc_7VnIe7G_MahexsbDyUa9W5eheE"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def generate_stable_id(name: str) -> str:
    """Generates a deterministic UUID based on a string name."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"nexus.skills.{name}"))


def parse_md_frontmatter(content: str) -> Dict[str, Any]:
    """Simple regex based frontmatter parser."""
    meta = {}
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if match:
        fm_content = match.group(1)
        for line in fm_content.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
    return meta


async def get_embedding(text: str) -> List[float]:
    """Generates embedding using OpenAI."""
    resp = await openai.AsyncOpenAI().embeddings.create(input=text, model="text-embedding-3-small")
    return resp.data[0].embedding


async def sync_skills():
    skills = []

    # 1. Load from registry.json
    registry_path = "backend/skills/registry.json"
    if os.path.exists(registry_path):
        with open(registry_path, "r") as f:
            registry_data = json.load(f)
            for item in registry_data:
                skill_id = item["id"]
                meta = item.get("metadata", {})
                skills.append(
                    {
                        "id": skill_id,
                        "name": meta.get("name", skill_id),
                        "description": meta.get("description", ""),
                        "role": meta.get("role", "Expert"),
                        "expertise": meta.get("expertise", []),
                        "content": meta.get("content", ""),
                        "source": "registry",
                    }
                )

    # 2. Scan _agents/skills for new skills
    agents_skills_dir = "_agents/skills"
    if os.path.exists(agents_skills_dir):
        for root, _, files in os.walk(agents_skills_dir):
            if "SKILL.md" in files:
                skill_path = os.path.join(root, "SKILL.md")
                skill_dir_name = os.path.basename(root)
                with open(skill_path, "r") as f:
                    content = f.read()
                    meta = parse_md_frontmatter(content)
                    skills.append(
                        {
                            "id": f"agent_{skill_dir_name}",
                            "name": meta.get("name", skill_dir_name),
                            "description": meta.get("description", ""),
                            "role": meta.get("role", "Process Expert"),
                            "expertise": meta.get("expertise", ["Standardized Procedure"]),
                            "content": content,
                            "source": "agent_directory",
                        }
                    )

    # Deduplicate skills by ID
    unique_skills = []
    seen_ids = set()
    for skill in skills:
        if skill["id"] not in seen_ids:
            unique_skills.append(skill)
            seen_ids.add(skill["id"])

    skills = unique_skills
    logger.info(f"Indexing {len(skills)} skills into Qdrant with stable IDs...")

    points = []
    for skill in skills:
        embed_text = (
            f"Skill: {skill['name']}\nRole: {skill['role']}\nDescription: {skill['description']}"
        )
        embedding = await get_embedding(embed_text)

        points.append(
            models.PointStruct(
                id=generate_stable_id(skill["id"]),  # Stable UUID
                vector=embedding,
                payload=skill,
            )
        )

    client.upsert(collection_name="nexus_skills", points=points)
    logger.info("Sync complete. nexus_skills updated with stable IDs.")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv("backend/.env")
    asyncio.run(sync_skills())
