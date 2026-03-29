from fastapi import APIRouter, HTTPException
from backend.database.supabase import get_async_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/tasks/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """
    Retrieve the status and results of a background ingestion task from Supabase.
    """
    try:
        async_supabase = await get_async_supabase()
        response = await async_supabase.table("ingestion_tasks").select("*").eq("id", task_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Task not found")
            
        task = response.data[0]
        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": task.get("progress", 0),
            "message": task.get("message", ""),
            "document_id": task.get("document_id"),
            "chunk_count": task.get("chunk_count")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching task status in routes_tasks for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching task status")
