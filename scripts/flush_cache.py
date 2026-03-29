import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.cache.semantic_cache import get_semantic_cache

def main():
    cache = get_semantic_cache()
    if not cache.redis:
        print("❌ Cache is disabled or Redis not connected.")
        return
    
    count = cache.flush_all()
    print(f"✅ Successfully purged {count} entries from the Semantic Cache.")

if __name__ == "__main__":
    main()
