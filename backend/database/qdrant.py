import logging

from qdrant_client import QdrantClient

from backend.config import settings

logger = logging.getLogger(__name__)

_qdrant_client = None


def get_qdrant() -> QdrantClient:
    """
    Returns a singleton Qdrant client.
    Initializes the client if it's the first call.
    """
    global _qdrant_client
    if _qdrant_client is None:
        if not settings.QDRANT_URL or not settings.QDRANT_API_KEY:
            logger.error("QDRANT_URL or QDRANT_API_KEY not configured.")
            raise ValueError("Qdrant configuration missing.")

        try:
            _qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
            logger.info("Successfully initialized Qdrant client.")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    return _qdrant_client


def init_qdrant_collection(collection_name: str = "nexus_chunks", vector_size: int = 384):
    """
    Initializes a Qdrant collection if it doesn't exist.
    Default vector_size 384 corresponds to all-MiniLM-L6-v2.
    """
    client = get_qdrant()
    from qdrant_client.http import models

    try:
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            logger.info(f"Creating Qdrant collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
        else:
            logger.debug(f"Qdrant collection {collection_name} already exists.")

    except Exception as e:
        logger.error(f"Error initializing Qdrant collection: {e}")
        raise
