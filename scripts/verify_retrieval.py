import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.retrieval.searcher import search_knowledge_base

async def main():
    query = "kashmira"
    print(f"--- Querying: {query} ---")
    
    chunks = await asyncio.to_thread(search_knowledge_base, query, 5)
    
    if not chunks:
        print("❌ No chunks found.")
    else:
        print(f"✅ Found {len(chunks)} chunks.")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i+1}:")
            print(f"  Title: {chunk.get('title')}")
            print(f"  Snippet: {chunk.get('text', '')[:100]}...")
            print(f"  Similarity: {chunk.get('similarity')}")

if __name__ == "__main__":
    asyncio.run(main())
