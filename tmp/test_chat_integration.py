import asyncio
import os
import sys
from dotenv import load_dotenv

print("Starting test script...")
load_dotenv()

# Set up logging to see errors
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Importing backend.database.chat...")
try:
    from backend.database.chat import create_conversation, save_message
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

async def test():
    try:
        print("Testing create_conversation...")
        conv_id = await create_conversation("Integration Test Thread")
        print(f"Conversation ID: {conv_id}")
        
        if conv_id:
            print("Testing save_message...")
            msg_id = await save_message(
                conversation_id=conv_id,
                role="user",
                content="Hello world test"
            )
            print(f"Message ID: {msg_id}")
        else:
            print("Failed to create conversation (returned None)")
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    print("Running asyncio event loop...")
    asyncio.run(test())
    print("Done.")
