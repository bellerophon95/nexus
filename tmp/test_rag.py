import time

import requests


def test_ask():
    url = "http://localhost:8000/api/ask"

    payload = {"query": "How is the Nexus ingestion pipeline verified?", "limit": 5, "rerank": True}

    print(f"Asking Project Nexus: '{payload['query']}'")

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            res = response.json()
            print(f"\nANWSER:\n{res['answer']}\n")
            print(f"Sources used: {len(res['context'])}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to connect to server: {e}")


if __name__ == "__main__":
    # Wait for server reload
    time.sleep(2)
    test_ask()
