
import asyncio
from dotenv import load_dotenv
load_dotenv()

from services.fetchers import fetch_newsdata, fetch_gnews
import httpx

async def test():
    async with httpx.AsyncClient(follow_redirects=True) as c:
        print("--- Testing Key 1 (US) ---")
        nd1 = await fetch_newsdata('us', c)
        print(f"Newsdata US (Key 1): {len(nd1)} articles")

        print("\n--- Testing Key 2 (Science) ---")
        nd2 = await fetch_newsdata('science', c)
        print(f"Newsdata Science (Key 2): {len(nd2)} articles")

        print("\n--- Testing GNews Key 2 (Entertainment) ---")
        # Entertainment maps to Key 2 in our logic (it's in categories, but not in key1_cats)
        gn = await fetch_gnews('entertainment', c)
        print(f"GNews Entertainment (Key 2): {len(gn)} articles")

if __name__ == "__main__":
    asyncio.run(test())
