import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.database.supabase import get_supabase

logger = logging.getLogger(__name__)

async def create_conversation(title: str) -> str:
    """
    Creates a new conversation and returns the ID.
    """
    try:
        data = {
            "title": title,
            "updated_at": datetime.utcnow().isoformat()
        }
        result = await asyncio.to_thread(
            lambda: get_supabase().table("conversations").insert(data).execute()
        )
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        return None

async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: List[Dict[str, Any]] = [],
    metrics: Dict[str, Any] = {},
    trace_id: Optional[str] = None
) -> str:
    """
    Saves a message turn to the database.
    """
    try:
        data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "citations": citations,
            "metrics": metrics,
            "trace_id": trace_id
        }
        result = await asyncio.to_thread(
            lambda: get_supabase().table("messages").insert(data).execute()
        )
        
        # Update conversation timestamp
        await asyncio.to_thread(
            lambda: get_supabase().table("conversations").update({
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", conversation_id).execute()
        )
        
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        return None

async def get_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieves recent conversations.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_supabase().table("conversations")
                .select("*")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return []

async def get_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all messages for a specific thread.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_supabase().table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to fetch messages for {conversation_id}: {e}")
        return []

async def update_message_feedback(message_id: str, feedback: int) -> bool:
    """
    Updates the human feedback score for a message.
    1 = Thumbs up, -1 = Thumbs down.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_supabase().table("messages")
                .update({"feedback": feedback})
                .eq("id", message_id)
                .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Failed to update feedback for {message_id}: {e}")
        return False

async def delete_conversation(conversation_id: str) -> bool:
    """
    Deletes a conversation. Messages are deleted via ON DELETE CASCADE in SQL.
    """
    try:
        result = await asyncio.to_thread(
            lambda: get_supabase().table("conversations")
                .delete()
                .eq("id", conversation_id)
                .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        return False
