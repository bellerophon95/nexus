import os
import httpx
import json
import sys

BASE_URL = os.getenv("BASE_URL", "https://project-nexus.duckdns.org")

def test_health():
    print(f"Checking health at {BASE_URL}/api/health...")
    try:
        response = httpx.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print(f"✅ Health OK: {response.json()}")
            return True
        else:
            print(f"❌ Health Failed (Status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def test_query():
    print(f"\nChecking RAG query at {BASE_URL}/api/query...")
    query = "What is Project Nexus?"
    try:
        # Use a timeout of 10s for the first response
        with httpx.stream("GET", f"{BASE_URL}/api/query", params={"q": query}, timeout=10.0) as response:
            if response.status_code != 200:
                print(f"❌ Query Failed (Status {response.status_code})")
                return False
            
            print("✅ Query Connection Established. Receiving tokens...")
            tokens_received = 0
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["type"] == "token":
                        tokens_received += 1
                    if data["type"] == "done":
                        print(f"✅ Query Completed. Received {tokens_received} tokens.")
                        return True
            
            if tokens_received > 0:
                print(f"⚠️ Query stream ended without 'done' event, but received {tokens_received} tokens.")
                return True
            return False
    except Exception as e:
        print(f"❌ Query Failed: {e}")
        return False

if __name__ == "__main__":
    success = True
    if not test_health():
        success = False
    
    if success and not test_query():
        success = False
        
    if success:
        print("\n🚀 ALL SMOKE TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n💥 SMOKE TESTS FAILED!")
        sys.exit(1)
