import requests
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000/api/ingest"
TEST_FILE = "scripts/test_search.py"  # Use an existing small file for testing
SESSION_ID = str(uuid.uuid4())

def test_ingest():
    print(f"--- Testing Ingest for Session: {SESSION_ID} ---")
    
    if not os.path.exists(TEST_FILE):
        print(f"Error: {TEST_FILE} not found.")
        return

    files = {
        'file': (os.path.basename(TEST_FILE), open(TEST_FILE, 'rb'), 'text/x-python')
    }
    
    # Passing is_personal as form data
    data = {
        'is_personal': 'true'
    }
    
    headers = {
        'X-Nexus-User-Id': SESSION_ID
    }
    
    try:
        response = requests.post(API_URL, files=files, data=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("SUCCESS: Ingestion started correctly with auth headers.")
            task_id = response.json().get("task_id")
            
            # Test status polling with auth headers
            status_url = f"http://localhost:8000/api/ingest/status/{task_id}"
            status_response = requests.get(status_url, headers=headers)
            print(f"Status Polling Code: {status_response.status_code}")
            print(f"Status Response: {status_response.json()}")
        else:
            print(f"FAILED: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ingest()
