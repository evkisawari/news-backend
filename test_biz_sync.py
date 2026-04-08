import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

async def test_biz():
    from services.fetchers import sync_category
    import httpx
    async with httpx.AsyncClient() as client:
        articles = await sync_category('business', client)
        print(f"Fetched {len(articles)} business articles")
        for a in articles[:3]:
            print(f"- {a['title']} ({a['source']})")

if __name__ == "__main__":
    asyncio.run(test_biz())
