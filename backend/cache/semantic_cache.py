import hashlib
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from upstash_redis import Redis
from backend.observability.tracing import observe
from backend.ingestion.embedder import generate_dense_embedding
from backend.config import settings

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(
        self, 
        redis_url: str = None, 
        redis_token: str = None, 
        similarity_threshold: float = 0.85, 
        ttl: int = 86400
    ):
        import os
        from dotenv import load_dotenv
        # Ensure we have the latest env vars if settings is stale
        load_dotenv(override=True)
        
        # Use lowercase attribute names as defined in config.py
        self.redis_url = redis_url or getattr(settings, "upstash_redis_rest_url", None) or os.getenv("UPSTASH_REDIS_REST_URL")
        self.redis_token = redis_token or getattr(settings, "upstash_redis_rest_token", None) or os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        
        if self.redis_url and self.redis_token:
            try:
                self.redis = Redis(url=self.redis_url, token=self.redis_token)
                # Test connection (quick ping)
                self.redis.set("nexus:cache_check", "connected", ex=10)
                logger.info(f"✅ Semantic Cache: Successfully connected to Upstash Redis ({self.redis_url[:20]}...)")
            except Exception as e:
                self.redis = None
                logger.error(f"❌ Semantic Cache Connection Failed: {e}")
        else:
            self.redis = None
            logger.warning("⚠️ Semantic Cache: Redis credentials missing (UPSTASH_REDIS_REST_URL/TOKEN). Cache disabled.")

    def _get_query_hash(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()

    @observe(name="cache_lookup")
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a cached answer if a semantically similar query exists.
        """
        if not self.redis:
            return None

        try:
            # 1. Embed current query
            query_embedding = generate_dense_embedding(query)
            if not query_embedding:
                return None
            
            # 2. Scan for cached query vectors
            # For a semantic cache in Redis without a vector plugin, we scan keys.
            # Upstash Redis is fast enough for small/medium caches.
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="cache:query:*", count=100)
                if not keys:
                    if cursor == 0: break
                    continue

                for key in keys:
                    cached_data_json = self.redis.get(key)
                    if not cached_data_json:
                        continue
                    
                    cached_data = json.loads(cached_data_json)
                    cached_embedding = cached_data.get("embedding")
                    
                    if cached_embedding:
                        # Compute Cosine Similarity
                        # Manual computation since we're using standard Redis
                        a = np.array(query_embedding)
                        b = np.array(cached_embedding)
                        
                        norm_a = np.linalg.norm(a)
                        norm_b = np.linalg.norm(b)
                        
                        if norm_a == 0 or norm_b == 0:
                            continue
                            
                        similarity = np.dot(a, b) / (norm_a * norm_b)
                        
                        if similarity >= self.similarity_threshold:
                            logger.info(f"Semantic Cache Hit! Similarity: {similarity:.4f}")
                            return cached_data
                
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Semantic Cache Lookup Error: {e}")
        
        return None

    @observe(name="cache_store")
    def set(
        self, 
        query: str, 
        answer: str, 
        citations: List[Dict[str, Any]], 
        doc_ids: List[str],
        metrics: Dict[str, Any] = None
    ):
        """
        Stores a query, answer, and its citations in the cache.
        """
        if not self.redis:
            return

        try:
            query_embedding = generate_dense_embedding(query)
            if not query_embedding:
                return
            
            cache_key = f"cache:query:{self._get_query_hash(query)}"
            data = {
                "query": query,
                "answer": answer,
                "citations": citations,
                "doc_ids": doc_ids,
                "embedding": query_embedding,
                "metrics": metrics
            }
            
            self.redis.set(cache_key, json.dumps(data), ex=self.ttl)
            logger.info(f"Stored query in Semantic Cache: {query[:50]}...")
        except Exception as e:
            logger.error(f"Semantic Cache Store Error: {e}")

    def invalidate_for_documents(self, doc_ids: List[str]):
        """
        Flushes cache entries that depend on the specified documents.
        """
        if not self.redis:
            return

        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="cache:query:*", count=100)
                if not keys:
                    if cursor == 0: break
                    continue

                for key in keys:
                    cached_data_json = self.redis.get(key)
                    if not cached_data_json:
                        continue
                    
                    cached_data = json.loads(cached_data_json)
                    cached_doc_ids = cached_data.get("doc_ids", [])
                    
                    if any(doc_id in cached_doc_ids for doc_id in doc_ids):
                        self.redis.delete(key)
                        count += 1
                
                if cursor == 0:
                    break
            if count > 0:
                logger.info(f"Invalidated {count} cache entries for docs: {doc_ids}")
        except Exception as e:
            logger.error(f"Semantic Cache Invalidation Error: {e}")

    def flush_all(self):
        """
        Clears all cached query-answer pairs from Redis.
        """
        if not self.redis:
            return

        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="cache:query:*", count=100)
                if not keys:
                    if cursor == 0: break
                    continue

                for key in keys:
                    self.redis.delete(key)
                    count += 1
                
                if cursor == 0:
                    break
            logger.info(f"✨ Purged {count} entries from Semantic Cache.")
            return count
        except Exception as e:
            logger.error(f"Semantic Cache Flush Error: {e}")
            return 0

_cache = None

def get_semantic_cache():
    global _cache
    if _cache is None:
        _cache = SemanticCache()
    return _cache
