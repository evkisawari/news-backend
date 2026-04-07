"""
services/scraper.py — Article content extraction using trafilatura.
"""
from typing import Optional
import trafilatura
import httpx

async def scrape_article(url: str, max_words: int = 250) -> Optional[str]:
    """
    Visit a URL and extract the main article text using trafilatura.
    Returns approximately the first `max_words` words.
    """
    if not url:
        return None

    try:
        # 1. Fetch the raw HTML (trafilatura can fetch, but we use httpx for better control)
        html = None
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            if resp.status_code == 200:
                html = resp.text
            else:
                print(f"[SCRAPER] HTTP {resp.status_code} for {url[:40]}")

        # 2. If httpx failed, try trafilatura's internal fetcher (sometimes handles JS better)
        if not html:
            html = trafilatura.fetch_url(url)
            
        if not html:
            return None

        # 3. Extract content using trafilatura
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        
        if not text or len(text) < 100:
            return None

        # 4. Trim to roughly max_words
        words = text.split()
        if len(words) > max_words:
            return " ".join(words[:max_words])
            
        return text

    except Exception as e:
        print(f"[SCRAPER] Error scraping {url[:50]}... : {e}")
        return None
