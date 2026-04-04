import logging
import os
import time
from collections.abc import Callable
from typing import Any

from backend.ingestion.chunker import semantic_chunking
from backend.ingestion.cleaner import clean_document
from backend.ingestion.parser import parse_document
from backend.ingestion.upserter import insert_chunks, upsert_document
from backend.observability.tracing import observe

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@observe(name="Prepare Ingestion")
def prepare_ingestion(
    file_path: str,
    title: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """
    Phase 1: Parse, Clean, and Chunk.
    Returns the list of chunks and document metadata.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"status": "error", "message": "File not found"}

    if title is None:
        title = os.path.basename(file_path)

    # 1. Parse Document
    start_time = time.time()
    logger.info(f"Pipeline stage: Parsing started for {file_path}")
    doc = parse_document(file_path, progress_callback=progress_callback)
    parse_time = time.time() - start_time
    logger.info(f"Pipeline stage: Parsing completed in {parse_time:.2f}s")

    # 2. Clean and Check for Duplicates
    if progress_callback:
        progress_callback(15.0)
    logger.info("Pipeline stage: Cleaning and deduplication...")
    metadata = {"title": title, "source_path": file_path}
    cleaned_doc = clean_document(doc.text, metadata)

    if cleaned_doc.is_duplicate:
        logger.info(
            f"Deduplication triggered: Document already exists (Fingerprint: {cleaned_doc.fingerprint})"
        )
        return {
            "status": "skipped",
            "reason": "near-duplicate",
            "fingerprint": str(cleaned_doc.fingerprint),
        }

    # 3. Semantic Chunking
    if progress_callback:
        progress_callback(20.0)
    logger.info("Pipeline stage: Starting semantic segmentation...")
    chunks = semantic_chunking(
        cleaned_doc.text,
        cleaned_doc.metadata,
        progress_callback=progress_callback,
        start_progress=20.0,
        end_progress=40.0,
    )
    logger.info(f"Pipeline stage: Generated {len(chunks)} chunks.")

    return {
        "status": "success",
        "chunks": chunks,
        "fingerprint": cleaned_doc.fingerprint,
        "title": title,
        "full_text": cleaned_doc.text,
    }


@observe(name="Process Single Chunk")
def process_single_chunk(chunk_text: str, token_count: int) -> dict[str, Any]:
    """
    Phase 2: Enrich and Embed a single chunk.
    """
    from backend.ingestion.embedder import embed_chunks_batch
    from backend.ingestion.enricher import enrich_chunks_batch

    # We use the batch versions for 1 item to maintain consistency
    batch_enrichments = enrich_chunks_batch([chunk_text])
    batch_embeddings = embed_chunks_batch([chunk_text])

    return {
        "text": chunk_text,
        "token_count": token_count,
        "entities": batch_enrichments[0]["entities"],
        "topics": batch_enrichments[0]["topics"],
        "key_phrases": batch_enrichments[0]["key_phrases"],
        "sparse_tokens": batch_embeddings[0]["sparse_tokens"],
        "embedding": batch_embeddings[0]["embedding"],
    }


@observe(name="Process Chunks Batch")
def process_chunks_batch(chunk_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Phase 2: Enrich and Embed a list of chunks efficiently.
    chunk_data should be a list of dicts with 'text' and 'token_count' keys,
    and optional 'metadata' for citation preservation.
    """
    from backend.ingestion.embedder import embed_chunks_batch
    from backend.ingestion.enricher import enrich_chunks_batch

    texts = [c["text"] for c in chunk_data]

    # Batch enrich and embed
    batch_enrichments = enrich_chunks_batch(texts)
    batch_embeddings = embed_chunks_batch(texts)

    results = []
    for i in range(len(chunk_data)):
        results.append(
            {
                "text": texts[i],
                "token_count": chunk_data[i]["token_count"],
                "metadata": chunk_data[i].get("metadata", {}),
                "entities": batch_enrichments[i]["entities"],
                "topics": batch_enrichments[i]["topics"],
                "key_phrases": batch_enrichments[i]["key_phrases"],
                "sparse_tokens": batch_embeddings[i]["sparse_tokens"],
                "embedding": batch_embeddings[i]["embedding"],
            }
        )
    return results


@observe(name="Finalize Ingestion")
def finalize_ingestion(
    full_text: str,
    title: str,
    file_path: str,
    fingerprint: int,
    chunk_count: int,
    user_id: str | None = None,
    is_personal: bool = True,
) -> str:
    """
    Phase 3: Generate summary and persist document metadata.
    Returns the document_id.
    """
    from backend.ingestion.summarizer import generate_summary

    logger.info("Pipeline stage: Generating document description...")
    description = generate_summary(full_text)

    doc_type = os.path.splitext(file_path)[1][1:].lower() or "unknown"

    doc_id = upsert_document(
        title=title,
        source_path=file_path,
        doc_type=doc_type,
        fingerprint=fingerprint,
        chunk_count=chunk_count,
        description=description,
        user_id=user_id,
        is_personal=is_personal,
    )

    # Cleanup temp file if it's in the uploads directory
    if "/tmp/uploads" in file_path or "tmp/uploads" in file_path:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temporary upload: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

    return doc_id


@observe(name="Monolithic Ingestion Pipeline")
def run_ingestion_pipeline(
    file_path: str,
    title: str | None = None,
    user_id: str | None = None,
    is_personal: bool = True,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """
    Legacy monolithic wrapper for small files or direct calls.
    Processes everything in a single sequence.
    """
    prep_result = prepare_ingestion(file_path, title, progress_callback)
    if prep_result["status"] != "success":
        return prep_result

    chunks = prep_result["chunks"]
    processed_chunks = []
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        processed = process_single_chunk(chunk.text, chunk.token_count)
        processed_chunks.append(processed)

        if progress_callback:
            progress_val = 40 + ((i + 1) / total_chunks) * 50
            progress_callback(min(progress_val, 90))

    doc_id = finalize_ingestion(
        full_text=prep_result["full_text"],
        title=prep_result["title"],
        file_path=file_path,
        fingerprint=prep_result["fingerprint"],
        chunk_count=len(processed_chunks),
        user_id=user_id,
        is_personal=is_personal,
    )

    insert_chunks(doc_id, processed_chunks, user_id=user_id, is_personal=is_personal)

    if progress_callback:
        progress_callback(100.0)

    return {
        "status": "success",
        "document_id": doc_id,
        "chunk_count": len(processed_chunks),
        "fingerprint": str(prep_result["fingerprint"]),
    }


if __name__ == "__main__":
    # Small local test if run directly
    import sys

    if len(sys.argv) > 1:
        result = run_ingestion_pipeline(sys.argv[1])
        print(result)
    else:
        print("Usage: python backend/ingestion/pipeline.py <file_path>")
