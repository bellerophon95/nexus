import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.database.supabase import get_supabase

logger = logging.getLogger(__name__)


async def sync_user(user_id: str, access_tier: str = "visitor") -> bool:
    """
    Upserts a shadow user record in the database.
    """
    try:
        data = {
            "id": user_id,
            "access_tier": access_tier,
            "last_seen": datetime.utcnow().isoformat(),
        }
        await asyncio.to_thread(lambda: get_supabase().table("users").upsert(data).execute())
        return True
    except Exception as e:
        logger.error(f"Failed to sync user {user_id}: {e}")
        return False


async def create_conversation(title: str, user_id: str | None = None) -> str:
    """
    Creates a new conversation and returns the ID.
    Now supports user_id for shadow auth isolation.
    """
    try:
        # We don't automatically call sync_user here to keep it lean,
        # but the API route will call it.
        data = {"title": title, "user_id": user_id, "updated_at": datetime.utcnow().isoformat()}
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
    citations: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    trace_id: str | None = None,
    agent_steps: list[dict[str, Any]] | None = None,
) -> str:
    """
    Saves a message turn to the database.
    Now includes agent_steps for persistent Logic/Citations view.
    """
    if agent_steps is None:
        agent_steps = []
    if metrics is None:
        metrics = {}
    if citations is None:
        citations = []
    try:
        data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "citations": citations,
            "metrics": metrics,
            "trace_id": trace_id,
            "agent_steps": agent_steps,
        }
        result = await asyncio.to_thread(
            lambda: get_supabase().table("messages").insert(data).execute()
        )

        # Update conversation timestamp
        await asyncio.to_thread(
            lambda: (
                get_supabase()
                .table("conversations")
                .update({"updated_at": datetime.utcnow().isoformat()})
                .eq("id", conversation_id)
                .execute()
            )
        )

        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        return None


async def get_conversations(user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """
    Retrieves recent conversations.
    Filters by user_id if provided (Critical for Shadow Auth).
    """
    try:
        query = get_supabase().table("conversations").select("*")

        if user_id:
            query = query.eq("user_id", user_id)
        else:
            # If no user_id is provided, we only return conversations that have NO user_id
            # This prevents public leakage of recruiter/private sessions.
            query = query.is_("user_id", "null")

        result = await asyncio.to_thread(
            lambda: query.order("updated_at", desc=True).limit(limit).execute()
        )
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to fetch conversations (user_id={user_id}): {e}")
        return []


async def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    """
    Retrieves all messages for a specific thread.
    """
    try:
        result = await asyncio.to_thread(
            lambda: (
                get_supabase()
                .table("messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .execute()
            )
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
            lambda: (
                get_supabase()
                .table("messages")
                .update({"feedback": feedback})
                .eq("id", message_id)
                .execute()
            )
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
            lambda: (
                get_supabase().table("conversations").delete().eq("id", conversation_id).execute()
            )
        )
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        return False
