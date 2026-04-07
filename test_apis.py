import asyncio
from dotenv import load_dotenv
load_dotenv()

from services.fetchers import fetch_newsdata, fetch_gnews
import httpx

async def test():
    async with httpx.AsyncClient(follow_redirects=True) as c:
        print("--- Testing Newsdata.io ---")
        nd = await fetch_newsdata('us', c)
        print(f"Newsdata US: {len(nd)} articles")
        if nd:
            print(f"  First title: {nd[0]['title'][:70]}")
            print(f"  Image URL:   {nd[0]['image'][:70]}")
            print(f"  Source:      {nd[0]['source']}")

        nd2 = await fetch_newsdata('world', c)
        print(f"Newsdata world: {len(nd2)} articles")

        print("\n--- Testing GNews ---")
        gn = await fetch_gnews('world', c)
        print(f"GNews world: {len(gn)} articles")
        if gn:
            print(f"  First title: {gn[0]['title'][:70]}")

asyncio.run(test())
