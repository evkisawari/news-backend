
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def debug_newsdata():
    key = os.getenv('NEWSDATA_KEY', '')
    print(f"Testing NewsData key: {key[:10]}...")
    
    url = "https://newsdata.io/api/1/news"
    params = {
        'apikey': key,
        'language': 'en',
        'category': 'top'
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

async def debug_gnews():
    key = os.getenv('GNEWS_API_KEY', '')
    print(f"\nTesting GNews key: {key[:10]}...")
    
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        'apikey': key,
        'lang': 'en',
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_newsdata())
    asyncio.run(debug_gnews())
