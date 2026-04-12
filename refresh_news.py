import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def manual_sync():
    print("[MANUAL SYNC] Starting full news fetch...")
    print("Connecting to Newsdata.io, GNews, RSS, and Reddit...")
    
    try:
        from services.fetchers import sync_all_categories
        await sync_all_categories()
        print("\n[SUCCESS] Sync complete! Your database is now up to date.")
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {e}")

if __name__ == "__main__":
    asyncio.run(manual_sync())
