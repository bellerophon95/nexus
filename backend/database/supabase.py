from supabase import create_client, Client, acreate_client, AsyncClient
from backend.config import settings

def get_supabase_client() -> Client:
    """
    Initializes and returns a Supabase client using the service role key
    for administrative privileges.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

async def get_async_supabase_client() -> AsyncClient:
    """
    Initializes and returns an asynchronous Supabase client.
    """
    return await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

supabase: Client = get_supabase_client()
# Note: async_supabase should be initialized in the app lifecycle or lazily
_async_supabase: AsyncClient = None

async def get_async_supabase():
    global _async_supabase
    if _async_supabase is None:
        _async_supabase = await get_async_supabase_client()
    return _async_supabase
