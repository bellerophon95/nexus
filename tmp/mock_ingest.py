import os
import sys

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from backend.ingestion.pipeline import run_ingestion_pipeline

mock_file = "mock_emergency_doc.txt"
with open(mock_file, "w") as f:
    f.write(
        "Project Nexus Emergency Fallback Document.\n\n"
        "This is an emergency document injected directly into the Supabase and Qdrant backend instances to bypass the standard API ingestion pipeline. "
        "The standard pipeline running on the EC2 instance experienced Out-Of-Memory (OOM) lockups while processing large PDF files due to uncapped Docker memory limits. "
        "This document ensures that semantic routing, Redis caching, and RAG retrieval continue to operate against verified data while the infrastructure is rebooted. "
        "Key systems: LangGraph for orchestration, Qdrant for vector search, Supabase for relational data and RLS, and Upstash for semantic cache hits."
    )

user_id = "b91f2259-0ba0-4e80-905c-c5337dd82843"

print("Running pipeline...")
result = run_ingestion_pipeline(
    file_path=mock_file,
    title="Emergency Fallback Guide",
    user_id=None,
    is_personal=False,
    progress_callback=lambda p: print(f"Progress: {p}%"),
)

print(result)
