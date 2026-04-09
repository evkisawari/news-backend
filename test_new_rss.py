
import asyncio
import httpx
from services.fetchers import _parse_rss_source_sync

async def test_rss():
    source = {'name': 'Middle East News', 'url': 'https://rss.app/feeds/DWxdxmyhM766QPLs.xml', 'category': 'world', 'weight': 1.4}
    async with httpx.AsyncClient() as client:
        resp = await client.get(source['url'], timeout=15)
        articles = _parse_rss_source_sync(source, resp.text)
        print(f"Fetched {len(articles)} articles from the new RSS feed.")
        if articles:
            for a in articles[:3]:
                print(f" - {a['title']} ({a.get('publishedAt')})")

if __name__ == "__main__":
    asyncio.run(test_rss())
