import asyncio
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.retrieval.searcher import search_knowledge_base

def test_rome_retrieval():
    print("🔎 Testing Retrieval for query: 'what do you know about rome'")
    
    # 1. Test with anonymous user (u_id = None)
    print("\n[Test 1] Anonymous User (Should see SHARED docs)")
    results = search_knowledge_base("what do you know about rome", user_id=None)
    
    if results:
        print(f"✅ Found {len(results)} results")
        for i, res in enumerate(results[:3]):
            title = res.get('metadata', {}).get('title', 'Unknown')
            is_personal = res.get('metadata', {}).get('is_personal')
            score = res.get('similarity') or res.get('score')
            print(f"  {i+1}. [{title}] is_personal={is_personal}, Score={score:.4f}")
            # print(f"     Content: {res.get('text')[:100]}...")
    else:
        print("❌ No results found for anonymous user.")

    # 2. Test with a random user ID (Should also see SHARED docs)
    print("\n[Test 2] Authenticated Random User (Should see SHARED docs)")
    results_random = search_knowledge_base("what do you know about rome", user_id="00000000-0000-0000-0000-000000000000")
    if results_random:
        print(f"✅ Found {len(results_random)} results")
    else:
        print("❌ No results found for authenticated user.")

if __name__ == "__main__":
    test_rome_retrieval()
