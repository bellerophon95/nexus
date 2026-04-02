import logging

from qdrant_client import QdrantClient

from backend.config import settings

logger = logging.getLogger(__name__)

_qdrant_client = None


def get_qdrant() -> QdrantClient:
    """
    Returns a singleton Qdrant client.
    Initializes the client if it's the first call.
    Uses in-memory fallback for development if cloud credentials fail.
    """
    global _qdrant_client
    if _qdrant_client is None:
        try:
            # Try cloud initialization first
            if settings.QDRANT_URL and settings.QDRANT_API_KEY:
                logger.info(f"Attempting to initialize Qdrant Cloud at {settings.QDRANT_URL}")
                _qdrant_client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                )
                # Verify connection
                _qdrant_client.get_collections()
                logger.info("Successfully connected to Qdrant Cloud.")
                return _qdrant_client
        except Exception as e:
            logger.error(f"Qdrant Cloud connection failed with credentials: {e}")
            # Do NOT fallback to :memory: silently if we were supposed to use cloud
            if settings.QDRANT_URL and settings.QDRANT_API_KEY:
                logger.critical(
                    "Qdrant Cloud credentials provided but connection failed. Not falling back to in-memory to avoid data loss/shadowing."
                )
                return None

        # Fallback to in-memory ONLY if no cloud config exists
        logger.info(
            "No Qdrant Cloud config found. Initializing in-memory Qdrant client for local testing."
        )
        _qdrant_client = QdrantClient(":memory:")

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
