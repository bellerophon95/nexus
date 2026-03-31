import logging

from fastapi import APIRouter, HTTPException

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
