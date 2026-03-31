from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from backend.api.security import rate_limit_dependency
from pydantic import BaseModel, Field
from typing import Optional, Dict
import shutil
import os
import uuid
import logging
import asyncio
from backend.ingestion.pipeline import run_ingestion_pipeline
from backend.cache.semantic_cache import get_semantic_cache
from backend.database.supabase import get_supabase, get_async_supabase

logger = logging.getLogger(__name__)
router = APIRouter()

class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., alias="id")
    status: str
    progress: float
    message: str
    document_id: Optional[str] = None
    chunk_count: Optional[int] = None

    class Config:
        populate_by_name = True

class IngestResponse(BaseModel):
    task_id: str
    status: str
    message: str

def process_ingestion_task(task_id: str, file_path: str, filename: str):
    """
    Background worker for document ingestion. Runs in a separate thread.
    Uses synchronous Supabase client for thread safety and to match pipeline IO.
    """
    try:
        get_supabase().table("ingestion_tasks").update({
            "status": "processing",
            "progress": 2.0
        }).eq("id", task_id).execute()
        
        logger.info(f"Starting ingestion task {task_id} for {filename}")
        
        # Define progress callback
        def update_progress(progress: float, message: str):
            get_supabase().table("ingestion_tasks").update({
                "progress": progress,
                "message": message
            }).eq("id", task_id).execute()

        # Run ingestion pipeline
        result = run_ingestion_pipeline(file_path, title=filename, progress_callback=update_progress)
        
        if result["status"] == "error":
            get_supabase().table("ingestion_tasks").update({
                "status": "error",
                "message": result.get("message", "Unknown pipeline error")
            }).eq("id", task_id).execute()
            return

        if result["status"] == "skipped":
            get_supabase().table("ingestion_tasks").update({
                "status": "skipped",
                "message": "Document already exists."
            }).eq("id", task_id).execute()
            return
            
        if result["status"] == "success":
            # Invalidate any cache entries for this document
            get_semantic_cache().invalidate_for_documents([result["document_id"]])
            get_supabase().table("ingestion_tasks").update({
                "status": "completed",
                "progress": 100.0,
                "document_id": result["document_id"],
                "chunk_count": result.get("chunk_count", 0),
                "message": f"Successfully ingested {filename}."
            }).eq("id", task_id).execute()

    except Exception as e:
        logger.error(f"Ingestion task {task_id} failed: {e}")
        try:
            get_supabase().table("ingestion_tasks").update({
                "status": "error",
                "message": str(e)
            }).eq("id", task_id).execute()
        except Exception as inner_e:
            logger.error(f"Could not even update error status for task {task_id}: {inner_e}")

@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    _ = Depends(rate_limit_dependency)
):
    """
    Ingests a document through the pipeline asynchronously.
    Enforces a 10MB limit to prevent OOM on Render Free Tier.
    """
    MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB
    
    try:
        # 1. Quick size check before saving to disk
        # Note: We take a slice to check size if the spooling didn't do it yet
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        
        if size > MAX_FILE_SIZE:
            logger.warning(f"File upload rejected: {file.filename} is {(size/1024/1024):.2f}MB (Max 10MB)")
            raise HTTPException(
                status_code=413, 
                detail=f"File too large ({(size/1024/1024):.1f}MB). The Free Tier limit is 10MB to prevent system instability."
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
        await async_supabase.table("ingestion_tasks").insert({
            "id": task_id,
            "status": "pending",
            "progress": 0,
            "filename": file.filename
        }).execute()
        
        # Add to background tasks (Runs in separate thread since process_ingestion_task is 'def')
        background_tasks.add_task(process_ingestion_task, task_id, file_path, file.filename)
        
        return IngestResponse(
            task_id=task_id,
            status="pending",
            message=f"Ingestion started for {file.filename}. Check status with task_id: {task_id}"
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
                detail="Backend configuration error: Invalid Supabase API Keys. Please check Render Environment Variables."
            )
            
        logger.error(f"Failed to start ingestion: {e}")
        raise HTTPException(status_code=500, detail=error_msg)
@router.get("/ingest/status/{task_id}")
async def get_ingest_status(task_id: str):
    """
    Retrieves the status and progress of a background ingestion task.
    """
    try:
        async_supabase = await get_async_supabase()
        response = await async_supabase.table("ingestion_tasks").select("*").eq("id", task_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Ingestion task not found")
            
        task = response.data[0]
        # Map DB 'id' to result 'task_id' for consistency with UI expectation
        return {
            "task_id": str(task["id"]),
            "status": task["status"],
            "progress": float(task.get("progress", 0)),
            "message": task.get("message", ""),
            "document_id": str(task.get("document_id")) if task.get("document_id") else None,
            "chunk_count": int(task.get("chunk_count", 0)) if task.get("chunk_count") else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching task status")
