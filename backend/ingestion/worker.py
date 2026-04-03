import datetime
import logging
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError

from backend.cache.semantic_cache import get_semantic_cache
from backend.database.supabase import get_supabase
from backend.ingestion.upserter import insert_chunks, upsert_document

logger = logging.getLogger(__name__)

_nlp_executor = None

import multiprocessing as mp


def get_nlp_executor():
    """Lazy loader for the NLP ProcessPoolExecutor to avoid 'spawn' deadlocks."""
    global _nlp_executor
    if _nlp_executor is None:
        logger.info("Initializing NLP Process Pool (max_workers=1)...")
        _nlp_executor = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"))
    return _nlp_executor


def _mark_task_error(supabase, task_id: str, message: str):
    """
    Helper to mark a task as error in Supabase.
    """
    try:
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        supabase.table("ingestion_tasks").update(
            {"status": "error", "message": message, "updated_at": now_iso}
        ).eq("id", task_id).execute()
        logger.error(f"Task {task_id} marked as error: {message}")
    except Exception as e:
        logger.error(f"Failed to mark task {task_id} as error: {e}")


def run_worker_loop():
    """
    Continuous background loop (Synchronous Thread) that processes pending chunks.
    Using a standard thread avoids asyncio event-loop conflicts on macOS.
    """
    global _nlp_executor
    logger.info("Nexus Ingestion Worker: Thread Started.")
    supabase = get_supabase()
    BATCH_SIZE = 10

    while True:
        try:
            # 1. Atomic Claim: Find and claim a batch of chunks
            rpc_response = supabase.rpc(
                "claim_ingestion_chunks", {"p_batch_size": BATCH_SIZE}
            ).execute()

            if not rpc_response.data or len(rpc_response.data) == 0:
                time.sleep(5)  # Wait for new work
                continue

            claimed_chunks = rpc_response.data
            logger.info(
                f"Worker Heartbeat: Claimed {len(claimed_chunks)} chunks (Processing batch...)"
            )

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

            # Signal activity by updating the task heartbeat before starting models
            now_iso = datetime.datetime.now(datetime.UTC).isoformat()
            for t_id in tasks_to_update:
                supabase.table("ingestion_tasks").update({"updated_at": now_iso}).eq(
                    "id", t_id
                ).execute()

            logger.info("Worker: Handoff batch to NLP Process Pool...")
            try:
                # Use the executor to run the batch processing in a separate process
                # We block the thread here, which is fine since it's a dedicated worker thread.
                # Wrap in timeout to prevent indefinite hangs
                try:
                    executor = get_nlp_executor()
                    future = executor.submit(process_chunks_batch, all_chunk_payloads)
                    processed_results = future.result(timeout=120)  # 2 minute timeout per batch
                    logger.info("Worker: NLP Process Pool completed successfully.")
                except (RuntimeError, BrokenPipeError):
                    logger.warning(
                        "Worker: NLP Executor crashed or broken. Recreating and retrying once..."
                    )
                    if _nlp_executor:
                        _nlp_executor.shutdown(wait=False, cancel_futures=True)
                        _nlp_executor = None
                    executor = get_nlp_executor()
                    future = executor.submit(process_chunks_batch, all_chunk_payloads)
                    processed_results = future.result(timeout=120)

            except TimeoutError:
                logger.error(
                    "Worker: NLP batch timed out after 120s. Marking affected tasks as error."
                )
                # We can't easily kill the stuck process without restarting the executor
                if _nlp_executor:
                    _nlp_executor.shutdown(wait=False, cancel_futures=True)
                    _nlp_executor = None
                for t_id in tasks_to_update:
                    _mark_task_error(
                        supabase,
                        t_id,
                        "Inference engine timed out (120s). Resource exhaustion or complex document structure.",
                    )
                continue  # Skip to next batch
            except Exception as e:
                logger.error(f"Worker: NLP Process Pool fatal crash: {e}")
                for t_id in tasks_to_update:
                    _mark_task_error(
                        supabase, t_id, f"Core processing engine failed: {str(e)[:200]}"
                    )
                continue

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

                    # Retry Task Update (Max 3 attempts)
                    for attempt in range(1, 4):
                        try:
                            supabase.table("ingestion_tasks").update(update_data).eq(
                                "id", task_id
                            ).execute()
                            logger.info(
                                f"Worker Progress: {update_data['progress']:.1f}% for task {task_id}"
                            )
                            break
                        except Exception as inner_e:
                            if attempt == 3:
                                raise inner_e
                            logger.warning(
                                f"Task update attempt {attempt} failed: {inner_e}. Retrying..."
                            )
                            time.sleep(1)

                except Exception as e:
                    logger.error(f"Failed to finalise a sub-batch for task {task_id}: {e}")

        except Exception as e:
            logger.error(f"Ingestion Worker Loop Error: {e}")
            time.sleep(5)


def run_worker_thread():
    """Entry point for the background thread."""
    logging.basicConfig(level=logging.INFO)
    run_worker_loop()


if __name__ == "__main__":
    run_worker_thread()
