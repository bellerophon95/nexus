import logging
import time
from fastapi import Request, HTTPException, status, Query
from typing import Optional
from upstash_redis import Redis
from backend.config import settings

logger = logging.getLogger(__name__)

# Re-use Redis connection logic
_redis = None

def get_redis():
    global _redis
    if _redis is None:
        if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
            try:
                _redis = Redis(url=settings.UPSTASH_REDIS_REST_URL, token=settings.UPSTASH_REDIS_REST_TOKEN)
            except Exception as e:
                logger.error(f"Failed to connect to Redis for Rate Limiting: {e}")
        else:
            logger.warning("Redis credentials missing. Rate limiting disabled.")
    return _redis

async def rate_limit_dependency(request: Request):
    """
    Dependency to enforce rate limiting per IP address.
    Uses sliding window log or simple counter in Redis.
    """
    redis = get_redis()
    if not redis:
        return # Skip if no redis
        
    # Simple IP-based rate limiting
    client_ip = request.client.host
    limit = settings.RATE_LIMIT_PER_MINUTE
    
    # Key format: ratelimit:ip:timestamp_minute
    current_minute = int(time.time() / 60)
    key = f"ratelimit:{client_ip}:{current_minute}"
    
    try:
        # Increment and set expiry (2 mins to be safe)
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 120)
            
        if count > limit:
            logger.warning(f"Rate limit exceeded for IP {client_ip}: {count}/{limit}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per minute allowed to protect engine resources."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # Fail open to allow service if Redis is flaky, or fail closed? 
        # For "Abuse Protection", failing open is better for UX, 
        # but the user wants to "protect accounts". 
        # Let's fail open but log it.
        pass

async def get_user_id(
    request: Request,
    user_id_query: Optional[str] = Query(None, alias="user_id")
) -> Optional[str]:
    """
    Extracts the shadow user ID from the request headers or query params (fallback for SSE).
    Used for session isolation without full login.
    """
    user_id = request.headers.get("X-Nexus-User-Id") or user_id_query
    if not user_id:
        return None
    return user_id
