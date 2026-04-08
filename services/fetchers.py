"""
services/fetchers.py — Multi-source news fetching pipeline.

Priority cascade per category:
  1. Newsdata.io  (primary   — structured, image-guaranteed)
  2. GNews        (secondary — fills gaps to TARGET_PER_CATEGORY)
  3. RSS feeds    (fallback  — only when articles < 10)

All fetchers return raw article dicts; processor.py normalizes them.
"""
import os
import re
import asyncio
from typing import List, Dict, Any

import httpx
import feedparser

from services.config import (
    CATEGORIES, NEWSDATA_CATEGORIES, GNEWS_TOPICS,
    RSS_SOURCES, SOURCE_WEIGHTS, TARGET_PER_CATEGORY,
)
from services.processor import (
    normalize_article, deduplicate, quality_filter,
    make_fingerprint, strip_html, clean_url, is_english, is_valid_image,
)
from services.scoring import calculate_score
from services.database import save_db

_RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/rss+xml, application/xml;q=0.9, */*;q=0.8',
}

_HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 NewsAggregator/2.0',
    'Accept': 'application/json',
}


# ══════════════════════════════════════════════
# STEP 2: NEWSDATA.IO (PRIMARY)
# ══════════════════════════════════════════════
async def fetch_newsdata(category: str, client: httpx.AsyncClient) -> List[Dict]:
    mapping = NEWSDATA_CATEGORIES.get(category, {'category': 'top', 'country': 'us'})
    params: Dict[str, str] = {
        'apikey':         os.getenv('NEWSDATA_KEY', ''),
        'language':       'en',
        'category':       mapping['category'],
        'image':          '1',         # Only articles with images
        'prioritydomain': 'top',
        'size':           '10',        # 10 per call (conserve quota)
    }
    # Only add country when non-empty (empty string causes 422)
    country = mapping.get('country', '')
    if country:
        params['country'] = country

    try:
        resp = await client.get(
            'https://newsdata.io/api/1/news',
            params=params,
            timeout=14.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get('status') != 'success':
            print(f"[NEWSDATA] Non-success for {category}: {data.get('message', '')}")
            return []

        articles = []
        for item in data.get('results', []):
            image = item.get('image_url', '')
            if not is_valid_image(image):
                continue

            url = clean_url(item.get('link', ''))
            title = (item.get('title') or '').strip()
            if not url or not title or not is_english(title):
                continue

            source = str(item.get('source_id') or item.get('source_name') or 'Newsdata')
            fp = make_fingerprint(title)
            articles.append({
                'title':       title,
                'description': strip_html(
                    item.get('description') or item.get('content') or ''
                )[:480],
                'url':        url,
                'source':     source,
                'category':   category,
                'publishedAt': item.get('pubDate', ''),
                'image':      image,
                '_fp':        fp,
                '_stableId':  fp,
                '_weight':    SOURCE_WEIGHTS.get(source, 1.0),
                '_sourceType':'newsdata',
            })

        print(f"[NEWSDATA] {category}: {len(articles)} articles")
        return articles

    except Exception as e:
        print(f"[NEWSDATA ERROR] {category}: {e}")
        return []


# ══════════════════════════════════════════════
# STEP 3: GNEWS (SECONDARY)
# ══════════════════════════════════════════════
async def fetch_gnews(category: str, client: httpx.AsyncClient) -> List[Dict]:
    topic = GNEWS_TOPICS.get(category, 'breaking-news')
    params = {
        'apikey': os.getenv('GNEWS_API_KEY', ''),
        'lang':   'en',
        'topic':  topic,
        'max':    '5',    # Keep low to conserve 100/day free-tier quota
    }

    try:
        resp = await client.get(
            'https://gnews.io/api/v4/top-headlines',
            params=params,
            timeout=12.0,
        )
        # 403/429 = free-tier rate limit; silently skip (RSS will cover)
        if resp.status_code in (403, 429):
            print(f'[GNEWS] Rate-limited for {category} ({resp.status_code}), skipping.')
            return []
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for item in data.get('articles', []):
            url = clean_url(item.get('url', ''))
            title = (item.get('title') or '').strip()
            image = item.get('image', '')
            if not url or not title or not is_english(title) or not is_valid_image(image):
                continue

            source_name = (item.get('source') or {}).get('name', 'GNews')
            fp = make_fingerprint(title)
            articles.append({
                'title':       title,
                'description': strip_html(item.get('description', '') or '')[:480],
                'url':         url,
                'source':      source_name,
                'category':    category,
                'publishedAt': item.get('publishedAt', ''),
                'image':       image,
                '_fp':         fp,
                '_stableId':   fp,
                '_weight':     SOURCE_WEIGHTS.get(source_name, 1.0),
                '_sourceType': 'gnews',
            })

        print(f"[GNEWS] {category}: {len(articles)} articles")
        return articles

    except Exception as e:
        print(f"[GNEWS ERROR] {category}: {e}")
        return []


# ══════════════════════════════════════════════
# STEP 4: RSS (FALLBACK)
# ══════════════════════════════════════════════
def _extract_rss_image(entry: Any) -> str:
    """Try every possible field to find a real article image."""
    # media:content / media:thumbnail
    for field in ['media_content', 'media_thumbnail']:
        items = entry.get(field, [])
        for m in (items if isinstance(items, list) else [items]):
            url = (m or {}).get('url', '')
            if is_valid_image(url):
                return url

    # enclosures
    for enc in entry.get('enclosures', []):
        url = (enc or {}).get('href', '') or (enc or {}).get('url', '')
        if is_valid_image(url):
            return url

    # Scan HTML body for <img src=...>
    body = ''
    content = entry.get('content', [])
    if content and isinstance(content, list):
        body = content[0].get('value', '')
    if not body:
        body = entry.get('summary', '')
    if body:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if match and is_valid_image(match.group(1)):
            return match.group(1)

    return ''


def _parse_rss_source_sync(source: Dict, xml_text: str) -> List[Dict]:
    """Synchronous feedparser call — parse string, no network."""
    try:
        feed = feedparser.parse(xml_text)
        articles = []
        for entry in feed.entries[:25]:
            title = (entry.get('title', '') or '').strip()
            url = clean_url(entry.get('link', ''))
            if not title or not url or not is_english(title):
                continue

            image = _extract_rss_image(entry)
            pub = entry.get('published', '') or entry.get('updated', '') or ''
            fp = make_fingerprint(title)
            articles.append({
                'title':       title,
                'description': strip_html(entry.get('summary', '') or '')[:480],
                'url':         url,
                'source':      source['name'],
                'category':    source['category'],
                'publishedAt': pub,
                'image':       image,
                '_fp':         fp,
                '_stableId':   fp,
                '_weight':     float(source.get('weight', 1.0)),
                '_sourceType': 'rss',
            })
        print(f"[RSS] {source['name']}: {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"[RSS ERROR] {source['name']}: {e}")
        return []


async def fetch_rss_for_category(category: str, client: httpx.AsyncClient) -> List[Dict]:
    loop = asyncio.get_event_loop()
    sources = [s for s in RSS_SOURCES if s['category'] == category]
    
    async def fetch_and_parse(src: Dict) -> List[Dict]:
        try:
            # Fetch with timeout to prevent indefinite hangs
            resp = await client.get(src['url'], headers=_RSS_HEADERS, timeout=12.0)
            resp.raise_for_status()
            text = resp.text
            # Parse in executor to avoid event loop blocking
            return await loop.run_in_executor(None, _parse_rss_source_sync, src, text)
        except httpx.TimeoutException:
            print(f"[RSS TIMEOUT] {src['name']} skipping...")
            return []
        except Exception as e:
            print(f"[RSS FETCH ERROR] {src['name']}: {e}")
            return []

    tasks = [fetch_and_parse(src) for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    articles = []
    for r in results:
        if isinstance(r, list):
            articles.extend(r)
    return articles


# ══════════════════════════════════════════════
# STEP 5: REDDIT (SUPPLEMENTAL)
# ══════════════════════════════════════════════
async def fetch_reddit_worldnews(client: httpx.AsyncClient) -> List[Dict]:
    """Fetch latest from r/worldnews JSON API."""
    url = "https://www.reddit.com/r/worldnews/new.json?limit=25"
    headers = {**_HTTP_HEADERS, 'User-Agent': 'PriorityNewsEngine/2.0 (by /u/NewsAppBot)'}
    
    try:
        resp = await client.get(url, headers=headers, timeout=12.0)
        resp.raise_for_status()
        data = resp.json()
        
        articles = []
        for post in data.get('data', {}).get('children', []):
            item = post.get('data', {})
            title = (item.get('title') or '').strip()
            url = clean_url(item.get('url', ''))
            
            if not title or not url or not is_english(title):
                continue
                
            # Skip reddit threads themselves, we want the external news link
            if 'reddit.com/r/worldnews' in url:
                continue

            image = item.get('thumbnail', '')
            if not is_valid_image(image):
                image = ''

            articles.append({
                'title':       title,
                'description': f"Reddit Discussion: {item.get('ups', 0)} upvotes. {item.get('num_comments', 0)} comments.",
                'url':         url,
                'source':      f"r/worldnews ({item.get('domain', 'reddit')})",
                'category':    'world',
                'publishedAt': datetime.fromtimestamp(item.get('created_utc', 0), timezone.utc).isoformat(),
                'image':       image,
                '_fp':         make_fingerprint(title),
                '_stableId':   make_fingerprint(title),
                '_weight':     1.2,
                '_sourceType': 'reddit',
            })
        print(f"[REDDIT] r/worldnews: {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"[REDDIT ERROR] {e}")
        return []


# ══════════════════════════════════════════════
# CATEGORY SYNC (Steps 2-8 per category)
# ══════════════════════════════════════════════
async def sync_category(category: str, client: httpx.AsyncClient) -> List[Dict]:
    articles: List[Dict] = []

    # Step 2: Primary
    nd = await fetch_newsdata(category, client)
    articles.extend(nd)

    # Step 3: Secondary — fill to target
    if len(articles) < TARGET_PER_CATEGORY:
        gn = await fetch_gnews(category, client)
        articles.extend(gn)

    # Step 4: RSS fallback — only when very sparse
    if len(articles) < 10:
        print(f"[SYNC] Falling back to RSS for {category}")
        rss = await fetch_rss_for_category(category, client)
        articles.extend(rss)

    # Deduplicate
    unique = deduplicate(articles)

    # Score
    scored = [{**a, '_score': calculate_score(a)} for a in unique]
    scored.sort(key=lambda x: x['_score'], reverse=True)

    print(f"[SYNC] {category}: {len(scored)} unique scored articles")
    return scored[:200]


# ══════════════════════════════════════════════
# FULL SYNC (Cron entrypoint)
# ══════════════════════════════════════════════
async def sync_all_categories():
    print('[CRON] ── Full priority sync starting ──')
    try:
        async with httpx.AsyncClient(
            headers=_HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            tasks = [sync_category(cat, client) for cat in CATEGORIES]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_articles: List[Dict] = []
            for i, r in enumerate(results):
                if isinstance(r, list):
                    all_articles.extend(r)
                else:
                    print(f"[SYNC ERROR] {CATEGORIES[i]}: {r}")

            # Step 5: Supplemental Reddit World News
            try:
                reddit = await fetch_reddit_worldnews(client)
                all_articles.extend(reddit)
            except Exception as e:
                print(f"[SUPPLEMENTAL ERROR] Reddit: {e}")

            # Step 8: Quality filter (requires valid image + description)
            quality = quality_filter(all_articles)

        # Global dedup across categories
        final = deduplicate(quality)
        final.sort(key=lambda x: x.get('_score', 0), reverse=True)

        # Step 9: Save
        save_db(final, sort=False)
        print(f'[CRON] ── Done. {len(final)} quality articles saved. ──')

    except Exception as e:
        print(f'[CRON ERROR] {e}')
