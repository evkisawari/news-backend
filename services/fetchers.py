import os
import re
import asyncio
import traceback
from datetime import datetime, timezone
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

def _get_api_key(service: str, category: str) -> str:
    key1_cats = ['us', 'world', 'technology', 'business']
    if service == 'newsdata':
        suffix = '1' if category in key1_cats else '2'
        return os.getenv(f'NEWSDATA_KEY_{suffix}') or os.getenv('NEWSDATA_KEY', '')
    if service == 'gnews':
        suffix = '1' if category in key1_cats else '2'
        return os.getenv(f'GNEWS_API_KEY_{suffix}') or os.getenv('GNEWS_API_KEY', '')
    return ""

# ══════════════════════════════════════════════
# NEWSDATA.IO
# ══════════════════════════════════════════════
async def fetch_newsdata(category: str, client: httpx.AsyncClient) -> List[Dict]:
    mapping = NEWSDATA_CATEGORIES.get(category, {'category': 'top', 'country': 'us'})
    params = {
        'apikey':         _get_api_key('newsdata', category),
        'language':       'en',
        'category':       mapping['category'],
        'image':          '1',
        'prioritydomain': 'top',
        'size':           '10',
    }
    country = mapping.get('country', '')
    if country: params['country'] = country

    try:
        resp = await client.get('https://newsdata.io/api/1/news', params=params, timeout=14.0)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'success': return []

        articles = []
        for item in data.get('results', []):
            if not isinstance(item, dict): continue
            normalized = normalize_article({
                'title':   item.get('title'),
                'url':     item.get('link'),
                'image':   item.get('image_url'),
                'description': item.get('description') or item.get('content'),
                'source':  item.get('source_id') or item.get('source_name'),
                'publishedAt': item.get('pubDate'),
                'category': category
            }, 'newsdata')
            if normalized: articles.append(normalized)
        return articles
    except Exception as e:
        print(f"[NEWSDATA ERROR] {category}: {e}")
        return []

# ══════════════════════════════════════════════
# GNEWS
# ══════════════════════════════════════════════
async def fetch_gnews(category: str, client: httpx.AsyncClient) -> List[Dict]:
    topic = GNEWS_TOPICS.get(category, 'world')
    params = {
        'apikey': _get_api_key('gnews', category),
        'lang':   'en',
        'topic':  topic,
        'max':    '10',
    }
    try:
        resp = await client.get('https://gnews.io/api/v4/top-headlines', params=params, timeout=12.0)
        resp.raise_for_status()
        data = resp.json()
        
        articles = []
        for item in data.get('articles', []):
            if not isinstance(item, dict): continue
            source_data = item.get('source')
            source_name = source_data.get('name') if isinstance(source_data, dict) else 'GNews'
            
            normalized = normalize_article({
                'title':   item.get('title'),
                'url':     item.get('url'),
                'image':   item.get('image'),
                'description': item.get('description'),
                'source':  source_name,
                'publishedAt': item.get('publishedAt'),
                'category': category
            }, 'gnews')
            if normalized: articles.append(normalized)
        return articles
    except Exception as e:
        print(f"[GNEWS ERROR] {category}: {e}")
        return []

# ══════════════════════════════════════════════
# RSS Fallback
# ══════════════════════════════════════════════
async def fetch_rss_for_category(category: str, client: httpx.AsyncClient) -> List[Dict]:
    sources = [s for s in RSS_SOURCES if s.get('category') == category]
    if not sources: return []
    
    all_rss = []
    for s in sources:
        url = s.get('url')
        weight = s.get('weight', 1.0)
        try:
            resp = await client.get(url, headers=_RSS_HEADERS, timeout=10.0)
            feed = feedparser.parse(resp.text)
            feed_title = feed.feed.get('title', 'RSS') if hasattr(feed.feed, 'get') else 'RSS'
            
            for entry in feed.entries[:25]:
                if not isinstance(entry, dict): continue
                img = ""
                if 'media_content' in entry and entry.media_content: 
                    img = entry.media_content[0].get('url', '')
                elif 'media_thumbnail' in entry and entry.media_thumbnail: 
                    img = entry.media_thumbnail[0].get('url', '')
                elif 'links' in entry:
                    for link in entry.links:
                        if 'image' in link.get('type', ''): img = link.get('href', '')
                
                normalized = normalize_article({
                    'title':   entry.get('title'),
                    'url':     entry.get('link'),
                    'image':   img,
                    'description': entry.get('summary') or entry.get('description'),
                    'source':  feed_title,
                    'publishedAt': entry.get('published') or entry.get('updated'),
                    'category': category,
                    '_weight': weight,
                }, 'rss')
                if normalized: all_rss.append(normalized)
        except Exception as e:
            print(f"[RSS ERROR] {url}: {e}")
    return all_rss

# ══════════════════════════════════════════════
# Reddit
# ══════════════════════════════════════════════
async def fetch_reddit_worldnews(client: httpx.AsyncClient) -> List[Dict]:
    try:
        resp = await client.get('https://www.reddit.com/r/worldnews/new.json?limit=30', timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for post in data.get('data', {}).get('children', []):
            item = post.get('data', {})
            if not isinstance(item, dict): continue
            url = clean_url(item.get('url', ''))
            if not url or 'reddit.com' in url: continue
            
            normalized = normalize_article({
                'title':   item.get('title'),
                'url':     url,
                'image':   item.get('thumbnail') if is_valid_image(item.get('thumbnail')) else None,
                'description': f"Reddit Discussion: {item.get('ups')} upvotes.",
                'source':  f"r/worldnews ({item.get('domain')})",
                'publishedAt': datetime.fromtimestamp(item.get('created_utc'), timezone.utc).isoformat(),
                'category': 'world'
            }, 'reddit')
            if normalized: articles.append(normalized)
        return articles
    except Exception as e:
        print(f"[REDDIT ERROR] {e}")
        return []

# ══════════════════════════════════════════════
# SYNC Logic
# ══════════════════════════════════════════════
async def sync_category(category: str, client: httpx.AsyncClient) -> List[Dict]:
    try:
        articles = []
        # Try all three sources
        articles.extend(await fetch_newsdata(category, client))
        articles.extend(await fetch_gnews(category, client))
        articles.extend(await fetch_rss_for_category(category, client))
        
        unique = deduplicate(articles)
        scored = []
        for a in unique:
            try:
                a['_score'] = calculate_score(a)
                scored.append(a)
            except Exception as e:
                print(f"[SCORE ERROR] {a.get('title')}: {e}")
        
        scored.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
        return scored[:100]
    except Exception as e:
        print(f"[CATEGORY SYNC ERROR] {category}: {e}")
        traceback.print_exc()
        return []

async def sync_all_categories():
    from dotenv import load_dotenv
    load_dotenv()
    print('[CRON] ── Starting Robust Standardized Sync ──')
    try:
        async with httpx.AsyncClient(headers=_HTTP_HEADERS, follow_redirects=True) as client:
            all_articles = []
            for cat in CATEGORIES:
                print(f"[CRON] ── Syncing: {cat.upper()} ──")
                results = []
                
                # Source 1: GNews (Best for Top Stories)
                try:
                    results += await fetch_gnews(cat, client)
                except Exception as e:
                    print(f"[GNEWS SKIP] {cat}: {e}")

                # Source 2: NewsData.io (Reliable Fallback)
                try:
                    results += await fetch_newsdata(cat, client)
                except Exception as e:
                    print(f"[NEWSDATA SKIP] {cat}: {e}")
                    
                # Source 3: RSS (Deep fallback)
                try:
                    results += await fetch_rss_for_category(cat, client)
                except Exception as e:
                    print(f"[RSS SKIP] {cat}: {e}")
                
                if not results:
                    continue
                all_articles.extend(results)
            
            reddit = await fetch_reddit_worldnews(client)
            for r in reddit: 
                r['_score'] = calculate_score(r)
            all_articles.extend(reddit)
            
            quality = quality_filter(all_articles)
            final = deduplicate(quality)
            
            # Sort by priority (Score DESC, then Date DESC)
            final.sort(key=lambda x: (x.get('_score', 0), x.get('publishedAt', '')), reverse=True)
            
            save_db(final, sort=False)
            print(f'[CRON] ── Finished. {len(final)} articles stored in PostgreSQL. ──')
    except Exception as e:
        print(f"[GLOBAL SYNC ERROR] {e}")
        traceback.print_exc()
