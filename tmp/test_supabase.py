import os

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"URL: {url}")
print(f"Key length: {len(key) if key else 0}")

supabase = create_client(url, key)

try:
    print("Fetching conversations...")
    result = supabase.table("conversations").select("*").limit(1).execute()
    print(f"Result: {result.data}")

    print("Testing insert...")
    test_data = {"title": "Test Title", "updated_at": "2026-03-28T20:40:00"}
    res = supabase.table("conversations").insert(test_data).execute()
    print(f"Insert Result: {res.data}")
except Exception as e:
    print(f"Error: {e}")
