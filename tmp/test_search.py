import time

import requests


def test_search():
    url = "http://localhost:8000/api/search"

    # Test query - looking for something we ingested in M2
    # "The industrial revolution was a period of global economic transition"
    # "A solar panel (also known as a PV panel) is a device that converts light into electricity"

    payload = {"query": "How does the Nexus ingestion pipeline work?", "limit": 5, "rerank": True}

    print(f"Testing search with query: '{payload['query']}'")

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            results = response.json()
            print(f"\nFound {len(results)} results:")
            for i, res in enumerate(results):
                similarity_str = f"Score: {res.get('similarity', 0):.4f}"
                rerank_score_str = (
                    f"| Rerank Score: {res.get('rerank_score', 0):.4f}"
                    if "rerank_score" in res
                    else ""
                )
                print(f"[{i+1}] {similarity_str} {rerank_score_str}")
                print(f"Text Snippet: {res['text'][:150]}...")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to connect to server: {e}")
    finally:
        # Give some time for background traces to be sent if any
        time.sleep(5)


if __name__ == "__main__":
    # Wait a bit for server to reload if it's running with --reload
    time.sleep(2)
    test_search()
