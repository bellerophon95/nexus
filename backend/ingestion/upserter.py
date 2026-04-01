import logging
from typing import Any

from backend.database.supabase import get_supabase
from backend.database.qdrant import get_qdrant, init_qdrant_collection
from qdrant_client import models
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)


@observe()
def upsert_document(
    title: str, source_path: str, doc_type: str, fingerprint: int, chunk_count: int
) -> str:
    """
    Upserts document metadata into Supabase and returns the document UUID.
    """
    try:
        data = {
            "title": title,
            "source_path": source_path,
            "doc_type": doc_type,
            "fingerprint": fingerprint,
            "chunk_count": chunk_count,
        }

        # Upsert based on fingerprint uniqueness
        response = (
            get_supabase().table("documents").upsert(data, on_conflict="fingerprint").execute()
        )

        if not response.data:
            logger.error(f"Supabase upsert returned no data: {response}")
            raise Exception("Failed to upsert document record.")

        doc_id = response.data[0]["id"]
        logger.info(f"Successfully upserted document: {title} (ID: {doc_id})")
        return doc_id
    except Exception as e:
        logger.error(f"Error upserting document: {e}")
        raise


@observe()
def insert_chunks(document_id: str, chunks_data: list[dict[str, Any]]):
    """
    Inserts a list of processed chunks into the chunks table in Supabase.
    Each item in chunks_data should match the chunks table schema.
    """
    try:
        # Prepare data with foreign key
        payload = []
        for chunk in chunks_data:
            item = {
                "document_id": document_id,
                "text": chunk["text"],
                "token_count": chunk["token_count"],
                "entities": chunk["entities"],
                "topics": chunk["topics"],
                "key_phrases": chunk["key_phrases"],
                "sparse_tokens": chunk["sparse_tokens"],
                "embedding": chunk["embedding"],
            }
            payload.append(item)

        if not payload:
            return

        # Supabase Batch insert
        response = get_supabase().table("chunks").insert(payload).execute()

        if not response.data:
            logger.error(f"Supabase chunk insert returned no data: {response}")
            raise Exception("Failed to insert chunks to Supabase.")

        # Qdrant Batch insert (Dual persistence)
        # Ensure collection exists first
        init_qdrant_collection()
        
        qdrant_points = []
        for i, chunk in enumerate(chunks_data):
            # Using the same metadata as Supabase for consistency
            point = models.PointStruct(
                id=response.data[i]["id"],  # Use Supabase UUID as Qdrant ID
                vector=chunk["embedding"],
                payload={
                    "document_id": document_id,
                    "text": chunk["text"],
                    "token_count": chunk["token_count"],
                    "entities": chunk["entities"],
                    "topics": chunk["topics"],
                    "key_phrases": chunk["key_phrases"],
                }
            )
            qdrant_points.append(point)

        if qdrant_points:
            get_qdrant().upsert(
                collection_name="nexus_chunks",
                points=qdrant_points
            )
            logger.info(f"Successfully upserted {len(qdrant_points)} points to Qdrant.")

        logger.info(f"Successfully inserted {len(payload)} chunks for document {document_id}")
    except Exception as e:
        logger.error(f"Error inserting chunks: {e}")
        raise
