import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from supabase import Client, create_client

load_dotenv()


def check_counts():
    print("--- Checking Counts ---")

    # 1. Check Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)

    res = (
        supabase.table("documents")
        .select("id, title, is_personal")
        .ilike("title", "%test_stress_ingestion_v3%")
        .execute()
    )
    print(f"Supabase Documents with 'test_stress_ingestion_v3': {res.data}")

    if res.data:
        doc_id = res.data[0]["id"]
        res_chunks = supabase.table("chunks").select("count").eq("document_id", doc_id).execute()
        print(f"Supabase Chunks for document {doc_id}: {res_chunks.data}")

    # 2. Check Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        print("QDRANT_URL not set.")
        return

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    try:
        collections = client.get_collections()
        print(f"Qdrant Collections: {collections}")

        count = client.count(collection_name="nexus_chunks")
        print(f"Qdrant Chunks Count: {count}")
    except Exception as e:
        print(f"Qdrant check failed: {e}")


if __name__ == "__main__":
    check_counts()
