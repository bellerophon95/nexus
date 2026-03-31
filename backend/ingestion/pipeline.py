import logging
import os
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


@observe(name="Ingestion Pipeline")
def run_ingestion_pipeline(
    file_path: str,
    title: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """
    Runs the full document ingestion pipeline:
    Parse -> Clean -> Chunk -> Enrich -> Embed -> Upsert

    Args:
        file_path: Path to the document file.
        title: Optional title for the document. Defaults to filename.

    Returns:
        Dict containing processing results (status, IDs, counts).
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return {"status": "error", "message": "File not found"}

    if title is None:
        title = os.path.basename(file_path)

    try:
        # 1. Parse Document
        import time

        start_time = time.time()
        logger.info(f"Pipeline stage: Parsing started for {file_path}")

        # Pass the progress_callback so parser can report sub-progress (5% to 15%)
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
        chunk_start_time = time.time()
        # Pass progress_callback to get updates during segment processing (20% - 40%)
        chunks = semantic_chunking(
            cleaned_doc.text,
            cleaned_doc.metadata,
            progress_callback=progress_callback,
            start_progress=20.0,
            end_progress=40.0,
        )
        chunk_time = time.time() - chunk_start_time
        logger.info(f"Pipeline stage: Generated {len(chunks)} chunks in {chunk_time:.2f}s.")

        # 4. Enrich and Embed each chunk
        logger.info(f"Pipeline stage: Enriching and embedding {len(chunks)} chunks in batches...")
        from backend.ingestion.embedder import embed_chunks_batch
        from backend.ingestion.enricher import enrich_chunks_batch

        processed_chunks = []
        total_chunks = len(chunks)
        BATCH_SIZE = 100

        for i in range(0, total_chunks, BATCH_SIZE):
            batch_chunks = chunks[i : i + BATCH_SIZE]
            batch_texts = [c.text for c in batch_chunks]

            # Batch Enrich (NER + Keywords)
            batch_enrichments = enrich_chunks_batch(batch_texts)
            # Batch Embed (Dense + Sparse)
            batch_embeddings = embed_chunks_batch(batch_texts)

            for j, chunk in enumerate(batch_chunks):
                chunk_data = {
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "entities": batch_enrichments[j]["entities"],
                    "topics": batch_enrichments[j]["topics"],
                    "key_phrases": batch_enrichments[j]["key_phrases"],
                    "sparse_tokens": batch_embeddings[j]["sparse_tokens"],
                    "embedding": batch_embeddings[j]["embedding"],
                }
                processed_chunks.append(chunk_data)

            # Update progress (Stages: 40% to 90%)
            if progress_callback:
                # Progress relative to chunks processed
                current_count = min(i + BATCH_SIZE, total_chunks)
                progress_val = 40 + (current_count / total_chunks) * 50
                progress_callback(min(progress_val, 90))

            logger.info(f"Batched {min(i + BATCH_SIZE, total_chunks)}/{total_chunks} chunks...")

        # 5. Persist to Database (Supabase)
        if progress_callback:
            progress_callback(95.0)
        logger.info("Pipeline stage: Persisting to Supabase...")
        db_start_time = time.time()
        doc_type = os.path.splitext(file_path)[1][1:].lower() or "unknown"

        doc_id = upsert_document(
            title=title,
            source_path=file_path,
            doc_type=doc_type,
            fingerprint=cleaned_doc.fingerprint,
            chunk_count=len(processed_chunks),
        )

        insert_chunks(doc_id, processed_chunks)
        time.time() - db_start_time

        logger.info(
            f"Pipeline completed successfully in {time.time() - start_time:.2f}s. Document ID: {doc_id}"
        )
        if progress_callback:
            progress_callback(100.0)

        return {
            "status": "success",
            "document_id": doc_id,
            "chunk_count": len(processed_chunks),
            "fingerprint": str(cleaned_doc.fingerprint),
        }

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Small local test if run directly
    import sys

    if len(sys.argv) > 1:
        result = run_ingestion_pipeline(sys.argv[1])
        print(result)
    else:
        print("Usage: python backend/ingestion/pipeline.py <file_path>")
