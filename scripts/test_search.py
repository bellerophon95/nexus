import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from dotenv import load_dotenv

from backend.retrieval.searcher import search_knowledge_base

logging.basicConfig(level=logging.INFO)
load_dotenv()


def test_search():
    query = "What do you know about test_stress_ingestion_v3.txt"
    print(f"--- Testing Search for: '{query}' ---")

    results = search_knowledge_base(query, user_id=None, limit=5)

    print(f"Results found: {len(results)}")
    for i, res in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"Title: {res.get('title')}")
        print(f"Score: {res.get('score')}")
        print(f"Text: {res.get('text')[:200]}...")


if __name__ == "__main__":
    test_search()
