import logging
import threading

from supabase import AsyncClient, Client, acreate_client, create_client

from backend.config import settings

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """
    Initializes and returns a Supabase client using the service role key.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in settings.")
        # We raise a more descriptive ValueError here instead of letting create_client crash
        raise ValueError(
            "Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required."
        )

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def get_async_supabase_client() -> AsyncClient:
    """
    Initializes and returns an asynchronous Supabase client.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in settings.")
        raise ValueError(
            "Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required."
        )

    return await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


# Thread-local storage for singletons to avoid deadlocks in multi-threaded contexts
_thread_local = threading.local()


def get_supabase() -> Client:
    """Get or initialize the synchronous Supabase client for the current thread."""
    if not hasattr(_thread_local, "supabase"):
        _thread_local.supabase = get_supabase_client()
    return _thread_local.supabase


async def get_async_supabase() -> AsyncClient:
    """Get or initialize the asynchronous Supabase client for the current thread."""
    if not hasattr(_thread_local, "async_supabase"):
        _thread_local.async_supabase = await get_async_supabase_client()
    return _thread_local.async_supabase
