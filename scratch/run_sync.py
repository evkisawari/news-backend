
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

# We MUST import services.models AFTER load_dotenv() if it uses os.getenv at top-level
from services.fetchers import sync_all_categories

if __name__ == "__main__":
    print("Starting manual sync from script...")
    asyncio.run(sync_all_categories())
    print("Sync finished.")
