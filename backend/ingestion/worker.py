import asyncio
import logging
from backend.database.supabase import get_supabase
from backend.ingestion.pipeline import process_single_chunk, finalize_ingestion
from backend.ingestion.upserter import insert_chunks, upsert_document
from backend.cache.semantic_cache import get_semantic_cache

logger = logging.getLogger(__name__)

async def run_worker_loop():
    """
    Continuous background loop that processes pending ingestion chunks.
    This runs in a dedicated asyncio task to avoid blocking the API.
    """
    logger.info("Nexus Ingestion Worker: Process Started.")
    supabase = get_supabase()

    while True:
        try:
            # 1. Atomic Claim: Find one 'pending' chunk
            # Note: In a production environment, we would use a more robust 'claim' 
            # mechanism, but for this single-worker setup, a simple fetch works.
            response = supabase.table("ingestion_chunks") \
                .select("*") \
                .eq("status", "pending") \
                .order("created_at") \
                .limit(1) \
                .execute()

            if not response.data:
                await asyncio.sleep(3)  # Wait for new work
                continue

            chunk_job = response.data[0]
            chunk_id = chunk_job["id"]
            task_id = chunk_job["task_id"]

            # Mark as processing immediately to prevent re-selection
            supabase.table("ingestion_chunks").update({"status": "processing"}).eq("id", chunk_id).execute()

            # 2. Process the Chunk (Enrich + Embed)
            logger.info(f"Worker: Processing chunk {chunk_job['chunk_index']} for task {task_id}")
            
            # Metadata lookup
            meta = chunk_job["metadata"]
            processed = process_single_chunk(chunk_job["content"], meta["token_count"])

            # 3. Ensure Document record exists
            task_response = supabase.table("ingestion_tasks").select("document_id, chunk_count, user_id").eq("id", task_id).execute()
            task_data = task_response.data[0]
            doc_id = task_data.get("document_id")

            if not doc_id:
                # First chunk of this task. Create the document record (without summary yet)
                import os
                doc_type = os.path.splitext(meta["file_path"])[1][1:].lower() or "unknown"
                
                doc_id = upsert_document(
                    title=meta["title"],
                    source_path=meta["file_path"],
                    doc_type=doc_type,
                    fingerprint=int(meta["fingerprint"]),
                    chunk_count=task_data["chunk_count"],
                    description="Processing...", # Placeholder
                    user_id=task_data["user_id"]
                )
                # Link doc to task
                supabase.table("ingestion_tasks").update({"document_id": doc_id}).eq("id", task_id).execute()

            # 4. Upsert to Vector DB (Qdrant + Postgres)
            insert_chunks(doc_id, [processed], user_id=task_data["user_id"])

            # 5. Update Status
            supabase.table("ingestion_chunks").update({"status": "completed"}).eq("id", chunk_id).execute()

            # 6. Check overall progress
            count_response = supabase.table("ingestion_chunks").select("id", count="exact").eq("task_id", task_id).eq("status", "completed").execute()
            completed_count = count_response.count
            total_count = task_data["chunk_count"]
            
            # Progress starts at 10% (parsing) and ends at 95% (chunks)
            progress = 10.0 + (completed_count / total_count) * 85.0 
            
            update_data = {"progress": min(progress, 95.0), "message": f"Processed {completed_count}/{total_count} chunks..."}
            
            if completed_count == total_count:
                # 7. Finalization: Summarize and Complete
                logger.info(f"Worker: Task {task_id} chunks complete. Finalizing...")
                final_doc_id = finalize_ingestion(
                    full_text=meta["full_text"],
                    title=meta["title"],
                    file_path=meta["file_path"],
                    fingerprint=int(meta["fingerprint"]),
                    chunk_count=total_count,
                    user_id=task_data["user_id"]
                )
                
                update_data["status"] = "completed"
                update_data["progress"] = 100.0
                update_data["message"] = f"Successfully ingested {meta['title']}."
                update_data["document_id"] = final_doc_id
                
                # Invalidate cache
                get_semantic_cache().invalidate_for_documents([final_doc_id])

            supabase.table("ingestion_tasks").update(update_data).eq("id", task_id).execute()

        except Exception as e:
            logger.error(f"Ingestion Worker Loop Error: {e}")
            if 'chunk_id' in locals():
                try:
                    supabase.table("ingestion_chunks").update({"status": "error", "error_message": str(e)}).eq("id", chunk_id).execute()
                except:
                    pass
            await asyncio.sleep(5)
