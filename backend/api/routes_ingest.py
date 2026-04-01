import asyncio
import logging
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.api.security import get_user_id, rate_limit_dependency
from backend.cache.semantic_cache import get_semantic_cache
from backend.database.supabase import get_async_supabase, get_supabase
from backend.ingestion.pipeline import prepare_ingestion, finalize_ingestion


def process_ingestion_task(
    task_id: str, file_path: str, filename: str, user_id: str, is_personal: bool = True
):
    """
    Producer: Splits the document into chunks and enqueues them in Supabase.
    Runs in a background thread to avoid blocking the upload response.
    """
    try:
        supabase = get_supabase()
        supabase.table("ingestion_tasks").update(
            {"status": "processing", "progress": 5.0, "message": "Analyzing document structure..."}
        ).eq("id", task_id).execute()

        logger.info(f"Producing ingestion tasks for {filename} (Task: {task_id})")

        # 1. Prepare (Parse + Clean + Chunk)
        result = prepare_ingestion(file_path, title=filename)

        if result["status"] == "error":
            supabase.table("ingestion_tasks").update(
                {"status": "error", "message": result.get("message", "Parsing error")}
            ).eq("id", task_id).execute()
            return

        if result["status"] == "skipped":
            supabase.table("ingestion_tasks").update(
                {"status": "skipped", "message": "Document already exists."}
            ).eq("id", task_id).execute()
            return

        chunks = result["chunks"]
        total_chunks = len(chunks)

        # 2. Queue Chunks in DB
        chunk_records = []
        for i, chunk in enumerate(chunks):
            chunk_records.append(
                {
                    "task_id": task_id,
                    "chunk_index": i,
                    "content": chunk.text,
                    "metadata": {
                        "token_count": chunk.token_count,
                        "fingerprint": str(result["fingerprint"]),
                        "title": result["title"],
                        "full_text": result["full_text"],  # Store for final summarization
                        "file_path": file_path,
                    },
                    "status": "pending",
                }
            )

        # Bulk insert chunks (Supabase handles up to a few thousand rows easily)
        # We do this in batches of 200 to be safe with payload sizes
        BATCH_SIZE = 200
        for i in range(0, len(chunk_records), BATCH_SIZE):
            batch = chunk_records[i : i + BATCH_SIZE]
            supabase.table("ingestion_chunks").insert(batch).execute()

        # 3. Update Task Status
        supabase.table("ingestion_tasks").update(
            {
                "status": "processing",
                "progress": 10.0,
                "chunk_count": total_chunks,
                "message": f"Queued {total_chunks} chunks for background processing.",
            }
        ).eq("id", task_id).execute()

        logger.info(f"Successfully enqueued {total_chunks} chunks for task {task_id}")

    except Exception as e:
        logger.error(f"Producer failed for task {task_id}: {e}")
        try:
            get_supabase().table("ingestion_tasks").update(
                {"status": "error", "message": f"Queueing failed: {str(e)}"}
            ).eq("id", task_id).execute()
        except Exception:
            pass


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    is_personal: bool = True,
    user_id: str = Depends(get_user_id),
    _=Depends(rate_limit_dependency),
):
    """
    Ingests a document through the pipeline asynchronously.
    Enforces a 10MB limit to prevent OOM on Render Free Tier.
    """
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    try:
        # 1. Quick size check before saving to disk
        # Note: We take a slice to check size if the spooling didn't do it yet
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)

        if size > MAX_FILE_SIZE:
            logger.warning(
                f"File upload rejected: {file.filename} is {(size / 1024 / 1024):.2f}MB (Max 10MB)"
            )
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({(size / 1024 / 1024):.1f}MB). The Free Tier limit is 10MB to prevent system instability.",
            )

        task_id = str(uuid.uuid4())
        async_supabase = await get_async_supabase()

        # Create temp directory
        temp_dir = "tmp/uploads"
        os.makedirs(temp_dir, exist_ok=True)

        # Save uploaded file
        file_ext = os.path.splitext(file.filename)[1]
        file_path = os.path.join(temp_dir, f"{task_id}{file_ext}")

        # Offload file IO to a thread to avoid blocking the event loop for large files
        def save_file():
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        await asyncio.to_thread(save_file)

        # Initialize task status in DB (Async)
        await (
            async_supabase.table("ingestion_tasks")
            .insert(
                {
                    "id": task_id,
                    "status": "pending",
                    "progress": 0,
                    "filename": file.filename,
                    "user_id": user_id,
                }
            )
            .execute()
        )

        # Add to background tasks (Runs in separate thread since process_ingestion_task is 'def')
        background_tasks.add_task(
            process_ingestion_task, task_id, file_path, file.filename, user_id, is_personal
        )

        return IngestResponse(
            task_id=task_id,
            status="pending",
            message=f"Ingestion started for {file.filename}. Check status with task_id: {task_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check specifically for Supabase 401/403 (Configuration Issues)
        if "401" in error_msg or "Invalid API key" in error_msg:
            logger.critical(f"SUPABASE CONFIG FAILURE: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail="Backend configuration error: Invalid Supabase API Keys. Please check Render Environment Variables.",
            )

        logger.error(f"Failed to start ingestion: {e}")
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/ingest/status/{task_id}")
async def get_ingest_status(task_id: str):
    """
    Retrieves the status and progress of a background ingestion task.
    Uses synchronous client in a thread to resolve async connection hangs.
    """
    try:

        def fetch_task():
            return get_supabase().table("ingestion_tasks").select("*").eq("id", task_id).execute()

        response = await asyncio.to_thread(fetch_task)

        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Ingestion task not found")

        task = response.data[0]
        return {
            "task_id": str(task["id"]),
            "status": task["status"],
            "progress": float(task.get("progress", 0)),
            "message": task.get("message", ""),
            "document_id": str(task.get("document_id")) if task.get("document_id") else None,
            "chunk_count": int(task.get("chunk_count", 0)) if task.get("chunk_count") else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch task status for {task_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error while fetching task status"
        )
