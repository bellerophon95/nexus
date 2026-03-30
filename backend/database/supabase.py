from supabase import create_client, Client, acreate_client, AsyncClient
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    """
    Initializes and returns a Supabase client using the service role key.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in settings.")
        # We raise a more descriptive ValueError here instead of letting create_client crash
        raise ValueError("Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required.")
    
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

async def get_async_supabase_client() -> AsyncClient:
    """
    Initializes and returns an asynchronous Supabase client.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in settings.")
        raise ValueError("Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required.")
        
    return await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

# Lazy singletons
_supabase: Client = None
_async_supabase: AsyncClient = None

def get_supabase() -> Client:
    """Get or initialize the synchronous Supabase client."""
    global _supabase
    if _supabase is None:
        _supabase = get_supabase_client()
    return _supabase

async def get_async_supabase() -> AsyncClient:
    """Get or initialize the asynchronous Supabase client."""
    global _async_supabase
    if _async_supabase is None:
        _async_supabase = await get_async_supabase_client()
    return _async_supabase
