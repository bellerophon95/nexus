import requests
import os
import uuid

url = "http://127.0.0.1:8000/api/ingest"
file_path = "tmp/test_api_ingestion.txt"

# Ensure tmp directory exists
os.makedirs("tmp", exist_ok=True)

# Create a unique file to avoid deduplication skip
unique_id = str(uuid.uuid4())
with open(file_path, "w") as f:
    f.write(f"Project Nexus API Test Document {unique_id}\n")
    f.write("This document is being processed via the FastAPI route to verify the end-to-end integration.")

print(f"Uploading {file_path} to {url}...")
with open(file_path, "rb") as f:
    files = {"file": (os.path.basename(file_path), f, "text/plain")}
    response = requests.post(url, files=files)

print(f"Status Code: {response.status_code}")
try:
    print(f"Response Body: {response.json()}")
except Exception as e:
    print(f"Failed to parse JSON response: {e}")
    print(f"Raw Response: {response.text}")
