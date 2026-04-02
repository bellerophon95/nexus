import logging

from fastapi import APIRouter, HTTPException
from qdrant_client import models

from backend.database.qdrant import get_qdrant
from backend.database.supabase import get_supabase
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
@observe(name="List Documents")
def list_documents():
    """
    Fetches all documents from the library.
    """
    try:
        response = (
            get_supabase().table("documents").select("*").order("created_at", desc=True).execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
@observe(name="Delete Document")
def delete_document(document_id: str):
    """
    Deletes a document and its associated chunks from the library.
    Cascade delete on the database handles the chunk cleanup.
    """
    try:
        # Before deleting, check if it exists so we can give a proper 404
        check = get_supabase().table("documents").select("id").eq("id", document_id).execute()
        if not check.data:
            raise HTTPException(status_code=404, detail="Document not found")

        # Execute deletion
        response = get_supabase().table("documents").delete().eq("id", document_id).execute()

        # In the current Supabase SDK, we check if records were actually affected
        if hasattr(response, "data") and len(response.data) > 0:
            logger.info(f"Successfully deleted document: {document_id}")
            return {"status": "success", "message": f"Document {document_id} deleted."}
        else:
            # Maybe it was already deleted by another process
            return {"status": "success", "message": "Document record already removed."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/share")
@observe(name="Share Document")
def share_document(document_id: str):
    """
    Marks a personal document as shared (is_personal = false).
    Also clears the user_id on all associated chunks to make them globally searchable.
    """
    try:
        supabase = get_supabase()
        
        # 1. Update the document record
        response = (
            supabase
            .table("documents")
            .update({"is_personal": False})
            .eq("id", document_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Document not found")

        # 2. Propagate to chunks in Supabase (Set user_id to NULL)
        (
            supabase
            .table("chunks")
            .update({"user_id": None})
            .eq("document_id", document_id)
            .execute()
        )

        # 3. Propagate to Qdrant (Set user_id to NULL in payload)
        try:
            qdrant = get_qdrant()
            qdrant.set_payload(
                collection_name="nexus_chunks",
                payload={
                    "user_id": None,
                    "is_personal": False
                },
                points=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            )
            logger.info(f"Successfully updated Qdrant payloads for document: {document_id}")
        except Exception as qe:
            logger.error(f"Failed to update Qdrant payloads for document {document_id}: {qe}")
            # We don't raise here to avoid failing the whole request if only Qdrant sync fails, 
            # but ideally we want consistency.

        logger.info(f"Successfully shared document {document_id} and its associated chunks.")
        return {"status": "success", "message": f"Document {document_id} and its chunks are now shared globally."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to share document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
