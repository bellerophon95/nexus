import logging
import time

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from upstash_redis import Redis

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
        try:
            if not settings.SUPABASE_JWT_SECRET:
                logger.warning("SUPABASE_JWT_SECRET not configured. Skipping JWT verification.")
                raise JWTError("Secret missing")

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
            logger.warning(f"JWT Verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Fallback to 'Shadow' ID (Transition mode / Guest sessions)
    # This allows the app to continue working while the frontend is being updated.
    legacy_user_id = request.headers.get("X-Nexus-User-Id") or user_id_query
    if legacy_user_id:
        return legacy_user_id

    # 3. Deny if neither is present (Once RLS is fully enforced)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a Bearer token or User ID.",
    )


async def get_user_id(user_id: str = Depends(get_current_user)) -> str:
    """Convenience dependency that returns just the validated user_id string."""
    return user_id
