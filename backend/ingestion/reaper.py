import datetime
import logging
import time

from backend.database.supabase import get_supabase

logger = logging.getLogger(__name__)


def run_reaper_loop():
    """
    Synchronous entry point for the reaper thread.
    """
    logger.info("Nexus Ingestion Reaper: Thread Started.")
    _reaper_monitor()


def _reaper_monitor():
    """
    Background loop (Synchronous Thread) that finds and resets 'Processing' tasks
    that haven't shown activity for more than the timeout threshold.
    """
    TIMEOUT_MINUTES = 2
    CHECK_INTERVAL = 30  # Faster checks

    while True:
        try:
            supabase = get_supabase()
            now = datetime.datetime.now(datetime.UTC)
            threshold = now - datetime.timedelta(minutes=TIMEOUT_MINUTES)

            # Query tasks that are stuck in 'processing' or 'pending'
            response = (
                supabase.table("ingestion_tasks")
                .select("id, status, updated_at, filename")
                .in_("status", ["processing", "pending"])
                .lt("updated_at", threshold.isoformat())
                .execute()
            )

            stale_tasks = response.data or []

            if stale_tasks:
                logger.warning(
                    f"Reaper: Found {len(stale_tasks)} stalled tasks. Attempting Recovery."
                )
                for task in stale_tasks:
                    task_id = task["id"]
                    filename = task.get("filename", "Unknown Document")

                    # Logic: If task is still 'processing' but inactive, try putting chunks back to pending ONE TIME
                    # before marking the task as error. This handles transient worker crashes.

                    # First, check if this task has chunks in 'processing'
                    chunk_res = (
                        supabase.table("ingestion_chunks")
                        .select("id")
                        .eq("task_id", task_id)
                        .eq("status", "processing")
                        .execute()
                    )
                    processing_chunks = chunk_res.data or []

                    if processing_chunks:
                        logger.warning(
                            f"Reaper: Task {task_id} ({filename}) is orphaned. Recycling {len(processing_chunks)} chunks to 'pending'."
                        )
                        supabase.table("ingestion_chunks").update(
                            {
                                "status": "pending",
                                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
                            }
                        ).eq("task_id", task_id).eq("status", "processing").execute()

                        # Update task timestamp so we don't recycle it again immediately
                        supabase.table("ingestion_tasks").update(
                            {
                                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
                                "message": "Reaper: Worker crash detected. Recycling chunks for re-pickup...",
                            }
                        ).eq("id", task_id).execute()
                    else:
                        # If no processing chunks, and it's still stuck, it's a terminal error
                        logger.error(
                            f"Reaper: Terminal failure forced for task {task_id} ({filename})"
                        )
                        supabase.table("ingestion_tasks").update(
                            {
                                "status": "error",
                                "message": f"Timed out: Ingestion worker unresponsive for > {TIMEOUT_MINUTES} minutes.",
                                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
                            }
                        ).eq("id", task_id).execute()

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Ingestion Reaper Loop Error: {e}")
            time.sleep(CHECK_INTERVAL)
