import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.security import get_user_id
from backend.database.chat import (
    get_conversations,
    get_message,
    get_messages,
    # Explicit import from chat.py for shadow auth sync
    sync_user,
    update_message_feedback,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    score: int  # 1 for up, -1 for down


@router.get("/conversations")
async def list_conversations(
    request: Request, limit: int = 20, user_id: str | None = Depends(get_user_id)
):
    """
    Returns a list of recent conversation threads.
    Now filtered by user_id for shadow auth.
    """
    # 2. List Threads
    try:
        # Shadow Auth: Sync user registration
        access_tier = request.headers.get("X-Nexus-Access-Tier") or "visitor"
        logger.info(f"Fetching history for user_id: {user_id} (Access Tier: {access_tier})")

        if user_id:
            await sync_user(user_id, access_tier)

        conversations = await get_conversations(user_id=user_id, limit=limit)
        logger.info(f"Retrieved {len(conversations)} threads for user {user_id}")
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Failed to list conversations for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str):
    """
    Returns the message history for a specific thread.
    """
    try:
        # Validate UUID format
        uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")

    try:
        messages = await get_messages(conversation_id)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Failed to fetch messages for {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(message_id: str, body: FeedbackRequest):
    """
    Submits user feedback for a specific message turn.
    Used to refine the LLM-as-a-judge.
    """
    try:
        # Validate UUID format
        uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID format")

    if body.score not in [1, -1, 0]:
        raise HTTPException(status_code=400, detail="Score must be 1, -1, or 0")

    try:
        success = await update_message_feedback(message_id, body.score)
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"status": "success", "message_id": message_id, "score": body.score}
    except Exception as e:
        logger.error(f"Failed to submit feedback for {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages/{message_id}")
async def get_message_details(message_id: str):
    """
    Returns the full details (including metrics) for a specific message.
    Used for polling evaluation results in the UI.
    """
    try:
        uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID format")

    try:
        msg = await get_message(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        return msg
    except Exception as e:
        logger.error(f"Failed to fetch message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_thread(conversation_id: str):
    """
    Deletes a conversation and its message history.
    """
    try:
        # Validate UUID format
        uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")

    try:
        from backend.database.chat import delete_conversation

        success = await delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
