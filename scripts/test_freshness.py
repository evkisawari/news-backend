
import httpx
import asyncio
from services.fetchers import sync_category

async def test():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print("Fetching fresh 'world' news locally...")
        news = await sync_category('world', client)
        print(f"Found {len(news)} articles.")
        for i, a in enumerate(news[:5]):
            print(f"[{i+1}] {a['publishedAt']} | {a['title'][:70]}...")

if __name__ == "__main__":
    asyncio.run(test())
