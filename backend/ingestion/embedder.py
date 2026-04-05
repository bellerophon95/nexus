import logging
import re
import time
from collections import Counter
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from backend.config import settings
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Cache for the OpenAI client
_client = None


def get_client():
    """Lazy loader for the OpenAI client."""
    global _client
    if _client is None:
        try:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                logger.error("OPENAI_API_KEY not found in settings.")
                raise ValueError("OPENAI_API_KEY is required for embedding generation.")
            _client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    return _client


@observe(name="Generate Dense Embedding")
def generate_dense_embedding(text: str, dimensions: int = 384) -> list[float]:
    """
    Generates a dense vector using OpenAI text-embedding-3-small.
    Default dimensions is 384 (matryoshka) to maintain local compatibility.
    Includes retry logic with exponential backoff.
    """
    if not text:
        return []

    client = get_client()
    max_retries = 3
    base_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                input=text, model="text-embedding-3-small", dimensions=dimensions
            )
            return response.data[0].embedding
        except (RateLimitError, APIConnectionError, APIStatusError) as e:
            if attempt == max_retries - 1:
                logger.error(f"OpenAI embedding failed after {max_retries} attempts: {e}")
                raise
            delay = base_delay * (2**attempt)
            logger.warning(f"OpenAI error (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error in generate_dense_embedding: {e}")
            raise


@observe(name="Generate Dense Embeddings Batch")
def generate_dense_embeddings_batch(texts: list[str], dimensions: int = 384) -> list[list[float]]:
    """
    Generates dense embeddings for a batch of texts using OpenAI.
    Optimizes for throughput and includes retry logic.
    """
    if not texts:
        return []

    client = get_client()
    max_retries = 3
    base_delay = 2.0
    OPENAI_BATCH_LIMIT = 2048

    all_embeddings = []

    # Process in chunks of 2048
    for i in range(0, len(texts), OPENAI_BATCH_LIMIT):
        batch_texts = texts[i : i + OPENAI_BATCH_LIMIT]

        batch_result = None
        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    input=batch_texts, model="text-embedding-3-small", dimensions=dimensions
                )
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_result = [item.embedding for item in sorted_data]
                break
            except (RateLimitError, APIConnectionError, APIStatusError) as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"OpenAI batch embedding failed at index {i} after {max_retries} attempts: {e}"
                    )
                    raise
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"OpenAI batch error at index {i} (attempt {attempt + 1}): {e}. Retrying in {delay}s..."
                )
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI batch execution at index {i}: {e}")
                raise

        if batch_result:
            all_embeddings.extend(batch_result)

    return all_embeddings


def generate_sparse_tokens(text: str) -> dict[str, int]:
    """
    Generates a sparse representation (bag-of-words) for the text.
    Used for hybrid search.
    """
    try:
        # Simple tokenization: lowercase, alphanumeric words
        words = re.findall(r"\b\w{2,}\b", text.lower())
        return dict(Counter(words))
    except Exception as e:
        logger.error(f"Sparse token generation failed: {e}")
        return {}


@observe()
def embed_chunk(text: str, dimensions: int = 384) -> dict[str, Any]:
    """
    Generates both dense and sparse embeddings for a single text chunk.
    """
    try:
        dense = generate_dense_embedding(text, dimensions=dimensions)
        sparse = generate_sparse_tokens(text)
        return {"embedding": dense, "sparse_tokens": sparse}
    except Exception as e:
        logger.error(f"Embedding chunk failed: {e}")
        raise


def embed_chunks_batch(texts: list[str], dimensions: int = 384) -> list[dict[str, Any]]:
    """
    Generates embeddings for a list of chunks efficiently.
    """
    try:
        dense_embeddings = generate_dense_embeddings_batch(texts, dimensions=dimensions)
        results = []
        for i, text in enumerate(texts):
            results.append(
                {"embedding": dense_embeddings[i], "sparse_tokens": generate_sparse_tokens(text)}
            )
        return results
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        raise
