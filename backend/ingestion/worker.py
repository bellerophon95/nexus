import asyncio
import logging

from backend.cache.semantic_cache import get_semantic_cache
from backend.database.supabase import get_supabase
from backend.ingestion.upserter import insert_chunks, upsert_document

logger = logging.getLogger(__name__)


async def run_worker_loop():
    """
    Continuous background loop that processes pending ingestion chunks in batches.
    Uses an atomic RPC function to claim chunks and avoid race conditions.
    """
    logger.info("Nexus Ingestion Worker: Process Started.")
    supabase = get_supabase()
    BATCH_SIZE = 10  # Optimal for balancing throughput and memory

    while True:
        try:
            # 1. Atomic Claim: Find and claim a batch of chunks
            rpc_response = supabase.rpc(
                "claim_ingestion_chunks", {"p_batch_size": BATCH_SIZE}
            ).execute()

            if not rpc_response.data or len(rpc_response.data) == 0:
                await asyncio.sleep(3)  # Wait for new work
                continue

            claimed_chunks = rpc_response.data
            logger.info(f"Worker: Claimed {len(claimed_chunks)} chunks for processing.")

            # 2. Prepare for batch processing
            # We group by task_id to handle multiple documents arriving at once
            tasks_to_update = {}
            for chunk in claimed_chunks:
                t_id = chunk["task_id"]
                if t_id not in tasks_to_update:
                    tasks_to_update[t_id] = []
                tasks_to_update[t_id].append(chunk)

            # 3. Batch Processing (Enrich + Embed)
            # Flattened list for the pipeline
            all_chunk_payloads = [
                {"text": c["content"], "token_count": c["metadata"]["token_count"]}
                for c in claimed_chunks
            ]

            from backend.ingestion.pipeline import process_chunks_batch

            processed_results = process_chunks_batch(all_chunk_payloads)

            # Map processed results back to original chunks
            for i, chunk in enumerate(claimed_chunks):
                chunk["processed"] = processed_results[i]

            # 4. Handle persistence for each task
            for task_id, task_chunks in tasks_to_update.items():
                try:
                    # Lookup Task/User metadata
                    task_response = (
                        supabase.table("ingestion_tasks")
                        .select("document_id, chunk_count, user_id, metadata, is_personal")
                        .eq("id", task_id)
                        .execute()
                    )
                    if not task_response.data:
                        logger.warning(f"Task {task_id} not found, skipping...")
                        continue

                    task_data = task_response.data[0]
                    doc_id = task_data.get("document_id")
                    is_personal = task_data.get("is_personal", True)

                    # Ensure document exists
                    meta = task_data.get("metadata", {})
                    if not doc_id and meta:
                        import os

                        doc_type = (
                            os.path.splitext(meta.get("file_path", ""))[1][1:].lower() or "unknown"
                        )
                        doc_id = upsert_document(
                            title=meta.get("title", "Untitled"),
                            source_path=meta.get("file_path", ""),
                            doc_type=doc_type,
                            fingerprint=int(meta["fingerprint"]) if meta.get("fingerprint") else 0,
                            chunk_count=task_data["chunk_count"],
                            description="Processing...",
                            user_id=task_data["user_id"],
                            is_personal=is_personal,
                        )
                        supabase.table("ingestion_tasks").update({"document_id": doc_id}).eq(
                            "id", task_id
                        ).execute()

                    # Upsert processed chunks in batch for this task
                    processed_batch = [c["processed"] for c in task_chunks]
                    insert_chunks(
                        doc_id,
                        processed_batch,
                        user_id=task_data["user_id"],
                        is_personal=is_personal,
                    )

                    # Mark chunks as completed
                    chunk_ids = [c["id"] for c in task_chunks]
                    supabase.table("ingestion_chunks").update({"status": "completed"}).in_(
                        "id", chunk_ids
                    ).execute()

                    # 5. Check overall status for this task
                    count_response = (
                        supabase.table("ingestion_chunks")
                        .select("id", count="exact")
                        .eq("task_id", task_id)
                        .eq("status", "completed")
                        .execute()
                    )
                    completed_count = count_response.count
                    total_count = task_data.get("chunk_count", 0)

                    if total_count > 0:
                        progress = 10.0 + (completed_count / total_count) * 85.0
                    else:
                        progress = 10.0

                    update_data = {
                        "progress": min(progress, 95.0),
                        "message": f"Processed {completed_count}/{total_count} chunks...",
                    }

                    if completed_count >= total_count:
                        from backend.ingestion.pipeline import finalize_ingestion

                        logger.info(f"Worker: Task {task_id} fully complete. Finalizing...")
                        final_doc_id = finalize_ingestion(
                            full_text=meta.get("full_text", ""),
                            title=meta.get("title", "Untitled"),
                            file_path=meta.get("file_path", ""),
                            fingerprint=int(meta["fingerprint"]) if meta.get("fingerprint") else 0,
                            chunk_count=total_count,
                            user_id=task_data["user_id"],
                            is_personal=is_personal,
                        )
                        update_data.update(
                            {
                                "status": "completed",
                                "progress": 100.0,
                                "message": f"Successfully ingested {meta.get('title', 'Document')}.",
                                "document_id": final_doc_id,
                            }
                        )
                        get_semantic_cache().invalidate_for_documents([final_doc_id])

                    supabase.table("ingestion_tasks").update(update_data).eq(
                        "id", task_id
                    ).execute()

                except Exception as e:
                    logger.error(f"Failed to finalise a sub-batch for task {task_id}: {e}")

        except Exception as e:
            logger.error(f"Ingestion Worker Loop Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker_loop())
