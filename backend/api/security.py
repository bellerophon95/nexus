import logging

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.config import settings

logger = logging.getLogger(__name__)

# Security schemes
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    token: HTTPAuthorizationCredentials | None = Depends(security),
    user_id_query: str | None = Query(None, alias="user_id"),
) -> str:
    """
    Verifies the Supabase JWT and returns the user_id.
    If no token is provided, it falls back to the legacy shadow header/query (for transition/SSE).
    """
    # 1. Try JWT Verification (Highest Priority)
    if token and token.credentials:
        if not settings.SUPABASE_JWT_SECRET:
            logger.warning("SUPABASE_JWT_SECRET not configured. Falling back to Shadow ID.")
        else:
            try:
                # Supabase JWTs use the 'HS256' algorithm
                payload = jwt.decode(
                    token.credentials,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                user_id = payload.get("sub")
                if user_id:
                    return user_id
            except JWTError as e:
                logger.warning(f"JWT Verification failed: {e}. Falling back to Shadow ID.")
                # We don't raise 401 yet, allowing fallback to X-Nexus-User-Id

    # 2. Fallback to 'Shadow' ID (Transition mode / Guest sessions)
    # This allows the app to continue working while the frontend is being updated.
    legacy_user_id = request.headers.get("X-Nexus-User-Id") or user_id_query

    if legacy_user_id and legacy_user_id.strip():
        uid = legacy_user_id.strip()
        logger.info(
            f"Resolved Identity: {uid} (via {'Header' if request.headers.get('X-Nexus-User-Id') else 'URL Param'})"
        )
        return uid

    # 3. Deny if neither is present (Once RLS is fully enforced)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a Bearer token or User ID.",
    )


async def get_user_id(user_id: str = Depends(get_current_user)) -> str:
    """Convenience dependency that returns just the validated user_id string."""
    return user_id


async def get_user_id_optional(
    request: Request, user_id_query: str | None = Query(None, alias="user_id")
) -> str | None:
    """
    Attempts to resolve user_id but does not raise 401 if missing.
    Useful for filtering public/private documents without forcing login.
    """
    try:
        # We reuse the logic but suppress the 401
        header_id = request.headers.get("X-Nexus-User-Id")
        return header_id or user_id_query
    except Exception:
        return None


async def rate_limit_dependency(request: Request):
    """
    Placeholder for rate limiting using settings.RATE_LIMIT_PER_MINUTE.
    Currently a no-op for local development.
    """
    # TODO: Implement Upstash-based rate limiting if needed
    return True
