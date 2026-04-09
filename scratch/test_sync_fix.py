from dotenv import load_dotenv
load_dotenv()

import asyncio
import httpx
from services.fetchers import sync_category
from services.database import save_db

async def manual_sync():
    print("Starting manual sync for 'technology'...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        articles = await sync_category('technology', client)
        print(f"Fetched {len(articles)} articles for technology.")
        if articles:
            print(f"Sample: {articles[0]['title']}")
            save_db(articles)
            print("Successfully saved and pushed to Firebase (if configured).")
        else:
            print("No articles fetched. Check logs for errors.")

if __name__ == "__main__":
    asyncio.run(manual_sync())
