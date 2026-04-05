import logging
from datetime import datetime
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_search_audit(query: str, user_id: str | None, filter_obj: Any, results_count: int):
    """
    Log structural details about the search to help debug the Search Gap.
    """
    timestamp = datetime.now().isoformat()
    log_msg = (
        f"\n[SEARCH AUDIT {timestamp}]\n"
        f"Query: {query}\n"
        f"User ID: {user_id if user_id else 'ANONYMOUS/NONE'}\n"
        f"Filter Applied: {filter_obj}\n"
        f"Results Found: {results_count}\n"
        "--------------------------------"
    )
    logger.info(log_msg)
